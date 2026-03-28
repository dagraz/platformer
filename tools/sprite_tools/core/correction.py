"""Geometric correction for scanned/photographed graph paper images.

Phase 3: Assesses distortion type (rotation vs perspective) from GridGeometry,
computes the appropriate transform matrix, and applies it to produce an
axis-aligned image suitable for projection-profile grid detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from sprite_tools.core.grid import GridGeometry, LineSegment, _segment_length


@dataclass
class CorrectionResult:
    """Output of geometric correction."""

    correction_type: str          # 'none' | 'rotation' | 'perspective'
    matrix: np.ndarray | None     # 2x3 affine or 3x3 homography
    rotation_degrees: float
    residual_px: float
    corrected_image: np.ndarray


def assess_distortion(
    geometry: GridGeometry,
    max_rotation: float = 15.0,
) -> tuple[str, dict]:
    """Determine distortion type from spatial angle variation.

    Uses the larger angle range (H or V) as the decisive signal:
      < 0.5 deg  -> 'none'
      < 2.0 deg  -> 'rotation'
      >= 2.0 deg -> 'perspective'

    Returns (type_str, stats_dict).
    """
    h_range = geometry.spatial_angles["horizontal"]["angle_range"]
    v_range = geometry.spatial_angles["vertical"]["angle_range"]
    max_range = max(h_range, v_range)

    # Check rotation magnitude
    h_angle = geometry.h_angle
    rotation = h_angle - 180 if h_angle > 90 else h_angle

    stats = {
        "h_angle_range": h_range,
        "v_angle_range": v_range,
        "max_angle_range": max_range,
        "rotation_estimate": rotation,
    }

    if abs(rotation) > max_rotation:
        # Too much rotation — likely not a grid image or badly skewed
        return ("none", stats)

    if max_range >= 2.0:
        return ("perspective", stats)
    elif max_range >= 0.5 or abs(rotation) > 0.3:
        return ("rotation", stats)
    else:
        return ("none", stats)


def compute_rotation_matrix(
    geometry: GridGeometry,
    image_shape: tuple[int, ...],
) -> np.ndarray:
    """Compute 2x3 affine rotation matrix to straighten the grid."""
    h, w = image_shape[:2]
    h_angle = geometry.h_angle
    rotation_angle = h_angle - 180 if h_angle > 90 else h_angle
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
    return matrix


def _cluster_positions(
    values: list[float],
    merge_thresh: float,
) -> list[tuple[float, float]]:
    """Greedy-merge sorted values into clusters.

    Returns list of (center, total_weight) where weight = count.
    """
    if not values:
        return []
    values = sorted(values)
    clusters: list[tuple[float, int]] = []
    cluster_sum = values[0]
    cluster_count = 1

    for i in range(1, len(values)):
        center = cluster_sum / cluster_count
        if values[i] - center <= merge_thresh:
            cluster_sum += values[i]
            cluster_count += 1
        else:
            clusters.append((cluster_sum / cluster_count, cluster_count))
            cluster_sum = values[i]
            cluster_count = 1
    clusters.append((cluster_sum / cluster_count, cluster_count))
    return clusters


def compute_perspective_matrix(
    geometry: GridGeometry,
    image_shape: tuple[int, ...],
) -> tuple[np.ndarray, tuple[int, int]]:
    """Compute 3x3 perspective matrix using outermost fragment clusters + zone angles.

    Returns (matrix, output_size).
    """
    h, w = image_shape[:2]

    # Filter to above-median weight fragments
    def above_median(frags: list[LineSegment]) -> list[LineSegment]:
        if not frags:
            return frags
        weights = [f.weight for f in frags]
        med = float(np.median(weights))
        return [f for f in frags if f.weight >= med]

    h_frags = above_median(geometry.h_fragments)
    v_frags = above_median(geometry.v_fragments)

    # Cluster H fragment y-midpoints
    merge_h = max(10.0, 0.005 * h)
    h_mids = [(f.y1 + f.y2) / 2 for f in h_frags]
    h_clusters = _cluster_positions(h_mids, merge_h)

    # Cluster V fragment x-midpoints
    merge_v = max(10.0, 0.005 * w)
    v_mids = [(f.x1 + f.x2) / 2 for f in v_frags]
    v_clusters = _cluster_positions(v_mids, merge_v)

    if len(h_clusters) < 2 or len(v_clusters) < 2:
        # Fallback: just return identity-like perspective
        pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        matrix = cv2.getPerspectiveTransform(pts, pts)
        return (matrix, (w, h))

    y_top = h_clusters[0][0]
    y_bottom = h_clusters[-1][0]
    x_left = v_clusters[0][0]
    x_right = v_clusters[-1][0]

    # Zone angles
    h_zones = geometry.spatial_angles["horizontal"]["zone_angles"]
    v_zones = geometry.spatial_angles["vertical"]["zone_angles"]

    # Construct lines with zone angles and intersect for 4 corners
    # H lines: top uses zone 0 angle, bottom uses zone 2 angle
    # V lines: left uses zone 0 angle, right uses zone 2 angle

    def angle_to_dir(angle_deg: float) -> tuple[float, float]:
        """Convert angle in degrees to unit direction vector."""
        rad = math.radians(angle_deg)
        return (math.cos(rad), math.sin(rad))

    def line_intersect(
        p1: tuple[float, float], d1: tuple[float, float],
        p2: tuple[float, float], d2: tuple[float, float],
    ) -> tuple[float, float]:
        """Intersect two lines: p1 + t*d1 = p2 + s*d2."""
        # d1.x * t - d2.x * s = p2.x - p1.x
        # d1.y * t - d2.y * s = p2.y - p1.y
        det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
        if abs(det) < 1e-10:
            # Parallel lines, return midpoint
            return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        t = (dx * (-d2[1]) - dy * (-d2[0])) / det
        return (p1[0] + t * d1[0], p1[1] + t * d1[1])

    # Use safe indexing for zone angles (fallback to dominant angle)
    def safe_zone(zones: list[float], idx: int, fallback: float) -> float:
        if idx < len(zones) and not math.isnan(zones[idx]):
            return zones[idx]
        return fallback

    h_top_angle = safe_zone(h_zones, 0, geometry.h_angle)
    h_bot_angle = safe_zone(h_zones, len(h_zones) - 1, geometry.h_angle)
    v_left_angle = safe_zone(v_zones, 0, geometry.v_angle)
    v_right_angle = safe_zone(v_zones, len(v_zones) - 1, geometry.v_angle)

    # Lines: point on position axis + direction from angle
    # Top H line: point at (w/2, y_top), direction from h_top_angle
    # Bottom H line: point at (w/2, y_bottom), direction from h_bot_angle
    # Left V line: point at (x_left, h/2), direction from v_left_angle
    # Right V line: point at (x_right, h/2), direction from v_right_angle

    top_pt = (w / 2, y_top)
    top_dir = angle_to_dir(h_top_angle)
    bot_pt = (w / 2, y_bottom)
    bot_dir = angle_to_dir(h_bot_angle)
    left_pt = (x_left, h / 2)
    left_dir = angle_to_dir(v_left_angle)
    right_pt = (x_right, h / 2)
    right_dir = angle_to_dir(v_right_angle)

    # 4 source corners: TL, TR, BR, BL
    tl = line_intersect(top_pt, top_dir, left_pt, left_dir)
    tr = line_intersect(top_pt, top_dir, right_pt, right_dir)
    br = line_intersect(bot_pt, bot_dir, right_pt, right_dir)
    bl = line_intersect(bot_pt, bot_dir, left_pt, left_dir)

    src_pts = np.float32([tl, tr, br, bl])

    # Destination: axis-aligned rectangle with average dimensions + margin
    avg_w = ((tr[0] - tl[0]) + (br[0] - bl[0])) / 2
    avg_h = ((bl[1] - tl[1]) + (br[1] - tr[1])) / 2
    margin = 10
    dst_pts = np.float32([
        [margin, margin],
        [margin + avg_w, margin],
        [margin + avg_w, margin + avg_h],
        [margin, margin + avg_h],
    ])

    out_w = int(round(avg_w + 2 * margin))
    out_h = int(round(avg_h + 2 * margin))

    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return (matrix, (out_w, out_h))


def _crop_to_content(image: np.ndarray, tolerance: int = 10) -> np.ndarray:
    """Trim uniform white/near-white borders after perspective warp."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mask = gray < (255 - tolerance)
    coords = np.argwhere(mask)
    if coords.size == 0:
        return image
    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0) + 1
    return image[y0:y1, x0:x1]


def apply_correction(
    image: np.ndarray,
    correction_type: str,
    matrix: np.ndarray | None,
    output_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Apply the computed correction to the image."""
    if correction_type == "none" or matrix is None:
        return image.copy()

    h, w = image.shape[:2]

    if correction_type == "rotation":
        result = cv2.warpAffine(
            image, matrix, (w, h),
            borderMode=cv2.BORDER_REPLICATE,
        )
        return result

    if correction_type == "perspective":
        if output_size is None:
            output_size = (w, h)
        result = cv2.warpPerspective(
            image, matrix, output_size,
            borderValue=(255, 255, 255),
        )
        result = _crop_to_content(result)
        return result

    return image.copy()


def _compute_residual(
    geometry: GridGeometry,
    correction_type: str,
    matrix: np.ndarray | None,
) -> float:
    """Estimate residual error after correction in pixels.

    Transforms fragment endpoints and measures remaining angle deviation
    from axis-aligned, converted to pixel displacement over typical length.
    """
    if correction_type == "none" or matrix is None:
        return 0.0

    # Sample some H fragments, transform their endpoints, measure remaining angle
    frags = geometry.h_fragments[:100]
    if not frags:
        return 0.0

    residuals = []
    for seg in frags:
        pts = np.float32([[seg.x1, seg.y1], [seg.x2, seg.y2]])
        if correction_type == "rotation":
            # Affine: add [0,0,1] row implicitly
            ones = np.ones((2, 1), dtype=np.float32)
            pts_h = np.hstack([pts, ones])  # (2, 3)
            transformed = pts_h @ matrix.T  # (2, 2)
        else:
            # Perspective
            pts_reshaped = pts.reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(pts_reshaped, matrix)
            transformed = transformed.reshape(-1, 2)

        dx = transformed[1, 0] - transformed[0, 0]
        dy = transformed[1, 1] - transformed[0, 1]
        length = math.hypot(dx, dy)
        if length > 0:
            # Residual angle from horizontal
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle > 90:
                angle = 180 - angle
            # Convert to pixel displacement at segment midpoint
            residuals.append(length * math.sin(math.radians(angle)))

    return float(np.median(residuals)) if residuals else 0.0


def correct_image(
    image: np.ndarray,
    geometry: GridGeometry,
    correction_type: str = "auto",
    max_rotation: float = 15.0,
) -> CorrectionResult:
    """Top-level correction: assess, compute, apply, measure.

    Args:
        image: BGR input image.
        geometry: Phase 2 GridGeometry.
        correction_type: 'auto', 'none', 'rotation', or 'perspective'.
        max_rotation: Maximum rotation angle in degrees to accept.

    Returns:
        CorrectionResult with corrected image and metadata.
    """
    if correction_type == "auto":
        correction_type, _stats = assess_distortion(geometry, max_rotation)

    h_angle = geometry.h_angle
    rotation_deg = h_angle - 180 if h_angle > 90 else h_angle

    matrix = None
    output_size = None

    if correction_type == "rotation":
        matrix = compute_rotation_matrix(geometry, image.shape)
    elif correction_type == "perspective":
        matrix, output_size = compute_perspective_matrix(geometry, image.shape)

    corrected = apply_correction(image, correction_type, matrix, output_size)
    residual = _compute_residual(geometry, correction_type, matrix)

    return CorrectionResult(
        correction_type=correction_type,
        matrix=matrix,
        rotation_degrees=rotation_deg,
        residual_px=residual,
        corrected_image=corrected,
    )
