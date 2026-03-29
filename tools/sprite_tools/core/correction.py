"""Geometric correction for scanned/photographed graph paper images.

Self-contained module that detects line segments, clusters them by angle,
assesses distortion type (rotation vs perspective), computes the appropriate
transform matrix, and applies it to produce an axis-aligned image suitable
for projection-profile grid detection.

No dependencies on other sprite_tools modules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class LineSegment:
    """A detected line segment with quality metadata."""

    x1: float
    y1: float
    x2: float
    y2: float
    angle: float    # degrees from horizontal, [0, 180)
    weight: float   # lsd_width * perpendicular_contrast


@dataclass
class CorrectionResult:
    """Output of geometric correction."""

    correction_type: str          # 'none' | 'rotation' | 'perspective'
    matrix: np.ndarray | None     # 2x3 affine or 3x3 homography
    rotation_degrees: float
    residual_px: float
    corrected_image: np.ndarray


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _segment_length(seg: LineSegment) -> float:
    """Euclidean length of a line segment."""
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def _angle_diff(a1: float, a2: float) -> float:
    """Smallest difference between two angles in [0, 180)."""
    d = abs(a1 - a2) % 180
    return min(d, 180 - d)


def _perpendicular_contrast(
    gray: np.ndarray, seg: LineSegment, n_samples: int = 21,
) -> float:
    """Sample intensity along perpendicular cross-section at segment midpoint.

    Measures local contrast across the line — higher contrast means the
    segment sits on a visible grid line rather than on noise or texture.
    """
    h, w = gray.shape[:2]
    mx, my = (seg.x1 + seg.x2) / 2, (seg.y1 + seg.y2) / 2
    angle_rad = math.radians(seg.angle)
    px, py = -math.sin(angle_rad), math.cos(angle_rad)

    half_span = 15
    intensities = []
    for i in range(n_samples):
        t = (i - n_samples // 2) * (2 * half_span / (n_samples - 1))
        sx = int(round(mx + t * px))
        sy = int(round(my + t * py))
        if 0 <= sx < w and 0 <= sy < h:
            intensities.append(float(gray[sy, sx]))

    if len(intensities) < 3:
        return 0.0

    arr = np.array(intensities)
    return max(0.0, float(np.median(arr)) - float(np.min(arr)))


def _weighted_median_angle(frags: list[LineSegment]) -> float:
    """Compute length-weighted median angle for a group of fragments.

    Handles wraparound near 0/180 degrees for near-horizontal lines.
    """
    if not frags:
        return 0.0

    angles = np.array([s.angle for s in frags])
    weights = np.array([_segment_length(s) for s in frags])

    # Unwrap: shift angles > 90 down by 180 to center near 0
    # (for near-horizontal lines that straddle the 0/180 boundary)
    median_raw = float(np.median(angles))
    if median_raw < 45 or median_raw > 135:
        unwrapped = np.where(angles > 90, angles - 180, angles)
    else:
        unwrapped = angles

    # Weighted median via sorted cumulative weights
    order = np.argsort(unwrapped)
    sorted_angles = unwrapped[order]
    sorted_weights = weights[order]
    cum_weights = np.cumsum(sorted_weights)
    half_weight = cum_weights[-1] / 2
    idx = int(np.searchsorted(cum_weights, half_weight))
    idx = min(idx, len(sorted_angles) - 1)
    result = float(sorted_angles[idx])

    # Re-wrap to [0, 180)
    return result % 180


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


def _spatial_angles(
    fragments: list[LineSegment],
    is_horizontal: bool,
    image_shape: tuple[int, int],
    n_zones: int = 3,
) -> dict:
    """Compute dominant angle per spatial zone along the line direction.

    For horizontal fragments, zones divide the image vertically (top/mid/bottom).
    For vertical fragments, zones divide horizontally (left/mid/right).

    Spatial variation in angle reveals perspective distortion:
    - Constant angle across zones -> pure rotation
    - Changing angle -> perspective (convergence)

    Returns dict with zone_angles, zone_counts, angle_range, angle_std.
    """
    h, w = image_shape
    dim = h if is_horizontal else w
    zone_size = dim / n_zones

    zone_angles: list[float] = []
    zone_counts: list[int] = []

    for z in range(n_zones):
        lo = z * zone_size
        hi = (z + 1) * zone_size

        zone_frags = []
        for seg in fragments:
            if is_horizontal:
                mid = (seg.y1 + seg.y2) / 2
            else:
                mid = (seg.x1 + seg.x2) / 2
            if lo <= mid < hi:
                zone_frags.append(seg)

        zone_counts.append(len(zone_frags))

        if zone_frags:
            angles = np.array([s.angle for s in zone_frags])
            weights = np.array([_segment_length(s) for s in zone_frags])

            # Unwrap for near-horizontal
            median_raw = float(np.median(angles))
            if median_raw < 45 or median_raw > 135:
                unwrapped = np.where(angles > 90, angles - 180, angles)
            else:
                unwrapped = angles

            weighted_mean = float(np.average(unwrapped, weights=weights)) % 180
            zone_angles.append(weighted_mean)
        else:
            zone_angles.append(float("nan"))

    # Compute variation
    valid_angles = [a for a in zone_angles if not math.isnan(a)]
    if len(valid_angles) >= 2:
        arr = np.array(valid_angles)
        if np.any(arr < 45) and np.any(arr > 135):
            arr = np.where(arr > 90, arr - 180, arr)
        angle_range = float(np.max(arr) - np.min(arr))
        angle_std = float(np.std(arr))
    else:
        angle_range = 0.0
        angle_std = 0.0

    return {
        "zone_angles": zone_angles,
        "zone_counts": zone_counts,
        "angle_range": angle_range,
        "angle_std": angle_std,
    }


def _angle_to_dir(angle_deg: float) -> tuple[float, float]:
    """Convert angle in degrees to unit direction vector."""
    rad = math.radians(angle_deg)
    return (math.cos(rad), math.sin(rad))


def _line_intersect(
    p1: tuple[float, float], d1: tuple[float, float],
    p2: tuple[float, float], d2: tuple[float, float],
) -> tuple[float, float]:
    """Intersect two lines: p1 + t*d1 and p2 + s*d2.

    Returns the intersection point, or the midpoint if lines are parallel.
    """
    det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
    if abs(det) < 1e-10:
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    t = (dx * (-d2[1]) - dy * (-d2[0])) / det
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_lines(
    image_gray: np.ndarray,
    min_length_frac: float = 0.5,
) -> list[LineSegment]:
    """Find line segments using LSD.

    Args:
        image_gray: Grayscale image (single channel uint8).
            If a BGR image is passed, it will be converted automatically.
        min_length_frac: Minimum segment length as a fraction of the smaller
            image dimension. Segments shorter than this are discarded.
            Set to a small value (e.g. 0.01) to keep short fragments,
            or 0 to keep all.

    Returns:
        List of LineSegment with weight = lsd_width * perpendicular_contrast.
    """
    if image_gray.ndim == 3:
        gray = cv2.cvtColor(image_gray, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_gray

    h, w = gray.shape[:2]
    min_length = max(5, int(min(h, w) * min_length_frac))

    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines_raw, widths, _, _ = lsd.detect(gray)

    if lines_raw is None:
        return []

    segments: list[LineSegment] = []
    for i, line in enumerate(lines_raw):
        x1, y1, x2, y2 = line[0]
        length = math.hypot(x2 - x1, y2 - y1)
        if length < min_length:
            continue

        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
        lsd_width = float(widths[i][0]) if widths is not None else 1.0

        seg = LineSegment(
            x1=float(x1), y1=float(y1),
            x2=float(x2), y2=float(y2),
            angle=angle, weight=lsd_width,
        )
        contrast = _perpendicular_contrast(gray, seg)
        seg.weight = lsd_width * contrast
        segments.append(seg)

    return segments


def cluster_by_angle(
    lines: list[LineSegment],
) -> tuple[list[LineSegment], list[LineSegment]]:
    """Separate line segments into near-horizontal and near-vertical groups.

    Builds a length-weighted angle histogram with 180 bins (1 degree each),
    smooths it with a Gaussian kernel, and finds the two dominant peaks.
    Each fragment is assigned to the nearest peak (within 20 degrees).

    Returns:
        (horizontal, vertical) — horizontal is the group closer to 0/180 deg.
    """
    if not lines:
        return ([], [])

    # Length-weighted histogram, 180 bins at 1 degree
    hist = np.zeros(180, dtype=np.float64)
    for seg in lines:
        length = _segment_length(seg)
        bin_idx = int(seg.angle) % 180
        hist[bin_idx] += length

    # Smooth with Gaussian (sigma=2 deg, circular via extension)
    extended = np.concatenate([hist, hist, hist])
    kernel = cv2.getGaussianKernel(13, 2.0).flatten()
    smoothed = np.convolve(extended, kernel, mode="same")[180:360]

    # Two highest peaks
    peak1 = int(np.argmax(smoothed))
    suppressed = smoothed.copy()
    for offset in range(-20, 21):
        suppressed[(peak1 + offset) % 180] = 0
    peak2 = int(np.argmax(suppressed))

    # Assign fragments, reject outliers > 20 degrees from nearest peak
    group1: list[LineSegment] = []
    group2: list[LineSegment] = []
    for seg in lines:
        d1 = _angle_diff(seg.angle, peak1)
        d2 = _angle_diff(seg.angle, peak2)
        if d1 <= d2:
            if d1 <= 20:
                group1.append(seg)
        else:
            if d2 <= 20:
                group2.append(seg)

    # Group closer to 0/180 deg is horizontal
    def horiz_dist(a: float) -> float:
        return min(a, 180 - a)

    if horiz_dist(peak1) <= horiz_dist(peak2):
        return (group1, group2)
    else:
        return (group2, group1)


def assess_distortion(
    h_lines: list[LineSegment],
    v_lines: list[LineSegment],
    image_shape: tuple[int, ...] | None = None,
    max_rotation: float = 15.0,
) -> tuple[str, dict]:
    """Determine distortion type from spatial angle variation.

    Computes per-zone angle statistics for each line group and uses
    the larger angle range as the decisive signal:
      < 0.5 deg  -> 'none'
      < 2.0 deg  -> 'rotation'
      >= 2.0 deg -> 'perspective'

    Args:
        h_lines: Near-horizontal line segments.
        v_lines: Near-vertical line segments.
        image_shape: (height, width) or (height, width, channels).
            If None, inferred from line segment bounding box.
        max_rotation: Maximum rotation angle (degrees) to accept.

    Returns:
        (type_str, stats_dict) where type_str is 'none', 'rotation',
        or 'perspective'.
    """
    # Infer image shape if not given
    if image_shape is None:
        all_segs = h_lines + v_lines
        if not all_segs:
            return ("none", {"h_angle_range": 0, "v_angle_range": 0,
                             "max_angle_range": 0, "rotation_estimate": 0})
        max_y = max(max(s.y1, s.y2) for s in all_segs)
        max_x = max(max(s.x1, s.x2) for s in all_segs)
        shape_2d = (int(max_y) + 1, int(max_x) + 1)
    else:
        shape_2d = (image_shape[0], image_shape[1])

    h_spatial = _spatial_angles(h_lines, is_horizontal=True, image_shape=shape_2d)
    v_spatial = _spatial_angles(v_lines, is_horizontal=False, image_shape=shape_2d)

    h_range = h_spatial["angle_range"]
    v_range = v_spatial["angle_range"]
    max_range = max(h_range, v_range)

    # Dominant horizontal angle -> rotation estimate
    h_angle = _weighted_median_angle(h_lines)
    rotation = h_angle - 180 if h_angle > 90 else h_angle

    stats = {
        "h_angle_range": h_range,
        "v_angle_range": v_range,
        "max_angle_range": max_range,
        "rotation_estimate": rotation,
        "h_spatial": h_spatial,
        "v_spatial": v_spatial,
    }

    if abs(rotation) > max_rotation:
        return ("none", stats)

    if max_range >= 2.0:
        return ("perspective", stats)
    elif max_range >= 0.5 or abs(rotation) > 0.3:
        return ("rotation", stats)
    else:
        return ("none", stats)


def compute_rotation(h_lines: list[LineSegment]) -> float:
    """Compute rotation angle from the horizontal line group.

    Returns the median angle of the horizontal group, expressed as
    degrees of rotation needed (positive = counterclockwise tilt).
    Near-zero for well-aligned images.
    """
    h_angle = _weighted_median_angle(h_lines)
    return h_angle - 180 if h_angle > 90 else h_angle


def find_grid_corners(
    h_lines: list[LineSegment],
    v_lines: list[LineSegment],
    image_shape: tuple[int, ...],
) -> np.ndarray:
    """Find four grid corners from outermost horizontal and vertical lines.

    Clusters line positions to find the outermost grid lines, then uses
    per-zone spatial angles to model each boundary line's direction and
    intersects them to produce four corner points.

    Args:
        h_lines: Near-horizontal line segments.
        v_lines: Near-vertical line segments.
        image_shape: (height, width, ...).

    Returns:
        4x2 float32 array of corner points [TL, TR, BR, BL].
    """
    h_img, w_img = image_shape[:2]

    # Filter to above-median weight fragments for robustness
    def above_median(frags: list[LineSegment]) -> list[LineSegment]:
        if not frags:
            return frags
        weights = [f.weight for f in frags]
        med = float(np.median(weights))
        return [f for f in frags if f.weight >= med]

    h_strong = above_median(h_lines)
    v_strong = above_median(v_lines)

    # Cluster H fragment y-midpoints to find top/bottom grid lines
    merge_h = max(10.0, 0.005 * h_img)
    h_mids = [(f.y1 + f.y2) / 2 for f in h_strong]
    h_clusters = _cluster_positions(h_mids, merge_h)

    # Cluster V fragment x-midpoints to find left/right grid lines
    merge_v = max(10.0, 0.005 * w_img)
    v_mids = [(f.x1 + f.x2) / 2 for f in v_strong]
    v_clusters = _cluster_positions(v_mids, merge_v)

    if len(h_clusters) < 2 or len(v_clusters) < 2:
        # Fallback: image corners
        return np.float32([
            [0, 0], [w_img, 0], [w_img, h_img], [0, h_img],
        ])

    y_top = h_clusters[0][0]
    y_bottom = h_clusters[-1][0]
    x_left = v_clusters[0][0]
    x_right = v_clusters[-1][0]

    # Zone angles for perspective modeling
    shape_2d = (h_img, w_img)
    h_spatial = _spatial_angles(h_lines, is_horizontal=True, image_shape=shape_2d)
    v_spatial = _spatial_angles(v_lines, is_horizontal=False, image_shape=shape_2d)
    h_zones = h_spatial["zone_angles"]
    v_zones = v_spatial["zone_angles"]

    h_dominant = _weighted_median_angle(h_lines)
    v_dominant = _weighted_median_angle(v_lines)

    def safe_zone(zones: list[float], idx: int, fallback: float) -> float:
        if idx < len(zones) and not math.isnan(zones[idx]):
            return zones[idx]
        return fallback

    h_top_angle = safe_zone(h_zones, 0, h_dominant)
    h_bot_angle = safe_zone(h_zones, len(h_zones) - 1, h_dominant)
    v_left_angle = safe_zone(v_zones, 0, v_dominant)
    v_right_angle = safe_zone(v_zones, len(v_zones) - 1, v_dominant)

    # Construct boundary lines and intersect for corners
    top_pt = (w_img / 2, y_top)
    top_dir = _angle_to_dir(h_top_angle)
    bot_pt = (w_img / 2, y_bottom)
    bot_dir = _angle_to_dir(h_bot_angle)
    left_pt = (x_left, h_img / 2)
    left_dir = _angle_to_dir(v_left_angle)
    right_pt = (x_right, h_img / 2)
    right_dir = _angle_to_dir(v_right_angle)

    tl = _line_intersect(top_pt, top_dir, left_pt, left_dir)
    tr = _line_intersect(top_pt, top_dir, right_pt, right_dir)
    br = _line_intersect(bot_pt, bot_dir, right_pt, right_dir)
    bl = _line_intersect(bot_pt, bot_dir, left_pt, left_dir)

    return np.float32([tl, tr, br, bl])


def compute_perspective_transform(
    corners: np.ndarray,
    image_shape: tuple[int, ...],
) -> np.ndarray:
    """Compute 3x3 homography mapping source corners to an axis-aligned rectangle.

    Args:
        corners: 4x2 float32 array [TL, TR, BR, BL] from find_grid_corners.
        image_shape: (height, width, ...) of the source image.

    Returns:
        3x3 perspective transform matrix.
    """
    tl, tr, br, bl = corners

    avg_w = ((tr[0] - tl[0]) + (br[0] - bl[0])) / 2
    avg_h = ((bl[1] - tl[1]) + (br[1] - tr[1])) / 2
    margin = 10

    dst_pts = np.float32([
        [margin, margin],
        [margin + avg_w, margin],
        [margin + avg_w, margin + avg_h],
        [margin, margin + avg_h],
    ])

    return cv2.getPerspectiveTransform(corners, dst_pts)


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
    """Apply rotation or perspective warp. Crop to grid boundary.

    Args:
        image: BGR input image.
        correction_type: 'none', 'rotation', or 'perspective'.
        matrix: 2x3 affine (rotation) or 3x3 homography (perspective).
        output_size: (width, height) for perspective output. If None,
            uses input image dimensions.

    Returns:
        Corrected image (cropped for perspective transforms).
    """
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


def compute_residual(
    corrected_image: np.ndarray,
    h_lines: list[LineSegment],
    v_lines: list[LineSegment],
    correction_type: str = "rotation",
    matrix: np.ndarray | None = None,
) -> float:
    """Mean deviation from perfect regular grid after correction.

    Transforms the original fragment endpoints through the correction matrix
    and measures remaining angle deviation from axis-aligned, converted to
    pixel displacement over typical segment length.

    Args:
        corrected_image: The corrected image (used for shape reference).
        h_lines: Original horizontal line segments (before correction).
        v_lines: Original vertical line segments (before correction).
        correction_type: 'none', 'rotation', or 'perspective'.
        matrix: The correction matrix that was applied.

    Returns:
        Median residual displacement in pixels.
    """
    if correction_type == "none" or matrix is None:
        return 0.0

    frags = h_lines[:100]
    if not frags:
        return 0.0

    residuals = []
    for seg in frags:
        pts = np.float32([[seg.x1, seg.y1], [seg.x2, seg.y2]])
        if correction_type == "rotation":
            ones = np.ones((2, 1), dtype=np.float32)
            pts_h = np.hstack([pts, ones])  # (2, 3)
            transformed = pts_h @ matrix.T  # (2, 2)
        else:
            pts_reshaped = pts.reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(pts_reshaped, matrix)
            transformed = transformed.reshape(-1, 2)

        dx = transformed[1, 0] - transformed[0, 0]
        dy = transformed[1, 1] - transformed[0, 1]
        length = math.hypot(dx, dy)
        if length > 0:
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle > 90:
                angle = 180 - angle
            residuals.append(length * math.sin(math.radians(angle)))

    return float(np.median(residuals)) if residuals else 0.0


# ---------------------------------------------------------------------------
# Top-level convenience function
# ---------------------------------------------------------------------------


def correct_image(
    image: np.ndarray,
    correction_type: str = "auto",
    max_rotation: float = 15.0,
    min_length_frac: float = 0.01,
) -> CorrectionResult:
    """Full correction pipeline: detect lines -> cluster -> assess -> compute -> apply.

    This is the main entry point. It runs the entire geometric correction
    pipeline on a single image and returns the corrected result.

    Args:
        image: BGR input image.
        correction_type: 'auto', 'none', 'rotation', or 'perspective'.
            When 'auto', the distortion type is determined from line analysis.
        max_rotation: Maximum rotation angle (degrees) to accept.
            Images rotated more than this are returned uncorrected.
        min_length_frac: Minimum line segment length as fraction of image
            dimension. Lower values detect more fragments but may include noise.

    Returns:
        CorrectionResult with corrected image and metadata.
    """
    # Detect and cluster
    lines = detect_lines(image, min_length_frac=min_length_frac)
    h_lines, v_lines = cluster_by_angle(lines)

    # Assess distortion
    if correction_type == "auto":
        correction_type, _stats = assess_distortion(
            h_lines, v_lines,
            image_shape=image.shape,
            max_rotation=max_rotation,
        )

    # Compute rotation estimate
    rotation_deg = compute_rotation(h_lines)

    matrix = None
    output_size = None

    if correction_type == "rotation":
        h, w = image.shape[:2]
        center = (w / 2, h / 2)
        matrix = cv2.getRotationMatrix2D(center, rotation_deg, 1.0)

    elif correction_type == "perspective":
        corners = find_grid_corners(h_lines, v_lines, image.shape)
        matrix = compute_perspective_transform(corners, image.shape)
        # Compute output size from corners
        tl, tr, br, bl = corners
        avg_w = ((tr[0] - tl[0]) + (br[0] - bl[0])) / 2
        avg_h = ((bl[1] - tl[1]) + (br[1] - tr[1])) / 2
        margin = 10
        output_size = (int(round(avg_w + 2 * margin)),
                       int(round(avg_h + 2 * margin)))

    corrected = apply_correction(image, correction_type, matrix, output_size)
    residual = compute_residual(
        corrected, h_lines, v_lines, correction_type, matrix,
    )

    return CorrectionResult(
        correction_type=correction_type,
        matrix=matrix,
        rotation_degrees=rotation_deg,
        residual_px=residual,
        corrected_image=corrected,
    )
