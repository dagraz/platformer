"""Grid line fragment analysis for scanned/photographed graph paper.

Phase 2: Detects LSD line fragments and extracts geometric properties
needed for correction — dominant grid angles, rough grid period, and
spatial angle variation (for perspective estimation).

Does NOT find precise grid positions — that requires axis-aligned lines
which only exist after Phase 3 geometric correction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


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
class GridGeometry:
    """Phase 2 output: geometric properties inferred from line fragments."""

    h_angle: float             # dominant horizontal direction (degrees)
    v_angle: float             # dominant vertical direction (degrees)
    h_period: float            # estimated grid spacing along H direction (pixels)
    v_period: float            # estimated grid spacing along V direction (pixels)
    h_fragments: list[LineSegment] = field(repr=False)
    v_fragments: list[LineSegment] = field(repr=False)
    spatial_angles: dict = field(default_factory=dict)


def _segment_length(seg: LineSegment) -> float:
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def _perpendicular_contrast(
    gray: np.ndarray, seg: LineSegment, n_samples: int = 21,
) -> float:
    """Sample intensity along perpendicular cross-section at segment midpoint."""
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


def _angle_diff(a1: float, a2: float) -> float:
    """Smallest difference between two angles in [0, 180)."""
    d = abs(a1 - a2) % 180
    return min(d, 180 - d)


def detect_fragments(
    image: np.ndarray,
    min_length: int = 5,
) -> list[LineSegment]:
    """Detect line segments using OpenCV LSD.

    Returns all segments above min_length with weight = lsd_width * contrast.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

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
    fragments: list[LineSegment],
) -> tuple[list[LineSegment], list[LineSegment]]:
    """Separate fragments into horizontal and vertical groups.

    Builds a length-weighted angle histogram, finds two dominant peaks,
    assigns each fragment to the nearest peak.

    Returns:
        (horizontal, vertical) — horizontal is the group closer to 0°/180°.
    """
    if not fragments:
        return ([], [])

    # Length-weighted histogram, 180 bins at 1°
    hist = np.zeros(180, dtype=np.float64)
    for seg in fragments:
        length = _segment_length(seg)
        bin_idx = int(seg.angle) % 180
        hist[bin_idx] += length

    # Smooth with Gaussian (sigma=2°, circular via extension)
    extended = np.concatenate([hist, hist, hist])
    kernel = cv2.getGaussianKernel(13, 2.0).flatten()
    smoothed = np.convolve(extended, kernel, mode="same")[180:360]

    # Two highest peaks
    peak1 = int(np.argmax(smoothed))
    suppressed = smoothed.copy()
    for offset in range(-20, 21):
        suppressed[(peak1 + offset) % 180] = 0
    peak2 = int(np.argmax(suppressed))

    # Assign fragments, reject outliers > 20°
    group1: list[LineSegment] = []
    group2: list[LineSegment] = []
    for seg in fragments:
        d1 = _angle_diff(seg.angle, peak1)
        d2 = _angle_diff(seg.angle, peak2)
        if d1 <= d2:
            if d1 <= 20:
                group1.append(seg)
        else:
            if d2 <= 20:
                group2.append(seg)

    # Group closer to 0°/180° is horizontal
    def horiz_dist(a: float) -> float:
        return min(a, 180 - a)

    if horiz_dist(peak1) <= horiz_dist(peak2):
        return (group1, group2)
    else:
        return (group2, group1)


def estimate_dominant_angles(
    h_fragments: list[LineSegment],
    v_fragments: list[LineSegment],
) -> tuple[float, float]:
    """Compute length-weighted median angle for each group."""

    def weighted_median_angle(frags: list[LineSegment]) -> float:
        if not frags:
            return 0.0
        # For angles near 0°/180°, unwrap to avoid wraparound artifacts
        angles = np.array([s.angle for s in frags])
        weights = np.array([_segment_length(s) for s in frags])

        # Unwrap: shift angles > 90 down by 180 to center near 0
        # (for near-horizontal lines that straddle the 0/180 boundary)
        median_raw = float(np.median(angles))
        if median_raw < 45 or median_raw > 135:
            # Near horizontal — unwrap angles > 90 to negative
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

    return (weighted_median_angle(h_fragments), weighted_median_angle(v_fragments))


def estimate_period(
    fragments: list[LineSegment],
    is_horizontal: bool,
    image_dim: int,
) -> float:
    """Estimate grid spacing from fragment position clustering.

    Projects fragments to their position axis (y for horizontal, x for vertical),
    clusters into position groups, and computes median spacing.
    """
    if len(fragments) < 4:
        return 0.0

    # Project to position axis
    positions: list[float] = []
    for seg in fragments:
        if is_horizontal:
            positions.append((seg.y1 + seg.y2) / 2)
        else:
            positions.append((seg.x1 + seg.x2) / 2)

    positions.sort()

    # Greedy cluster (merge within 0.5% of image_dim, min 10px)
    merge_thresh = max(10.0, 0.005 * image_dim)
    clusters: list[float] = []
    cluster_sum = positions[0]
    cluster_count = 1

    for i in range(1, len(positions)):
        center = cluster_sum / cluster_count
        if positions[i] - center <= merge_thresh:
            cluster_sum += positions[i]
            cluster_count += 1
        else:
            clusters.append(cluster_sum / cluster_count)
            cluster_sum = positions[i]
            cluster_count = 1
    clusters.append(cluster_sum / cluster_count)

    if len(clusters) < 3:
        return 0.0

    # Median spacing between consecutive clusters
    spacings = [clusters[i + 1] - clusters[i] for i in range(len(clusters) - 1)]
    return float(np.median(spacings))


def estimate_spatial_angles(
    fragments: list[LineSegment],
    is_horizontal: bool,
    image_shape: tuple[int, int],
    n_zones: int = 3,
) -> dict:
    """Compute dominant angle per spatial zone along the line direction.

    For horizontal fragments, zones divide the image vertically (top/mid/bottom).
    For vertical fragments, zones divide horizontally (left/mid/right).

    Spatial variation in angle reveals perspective distortion:
    - Constant angle across zones → pure rotation
    - Changing angle → perspective (convergence)

    Returns dict with zone angles and variation stats.
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
        # Unwrap for comparison
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


def analyze_grid_geometry(image: np.ndarray) -> GridGeometry:
    """Full Phase 2 pipeline: detect fragments → cluster → estimate geometry.

    Args:
        image: BGR image.

    Returns:
        GridGeometry with dominant angles, periods, fragments, and spatial model.
    """
    h, w = image.shape[:2]

    fragments = detect_fragments(image)
    h_frags, v_frags = cluster_by_angle(fragments)
    h_angle, v_angle = estimate_dominant_angles(h_frags, v_frags)
    h_period = estimate_period(h_frags, is_horizontal=True, image_dim=h)
    v_period = estimate_period(v_frags, is_horizontal=False, image_dim=w)

    h_spatial = estimate_spatial_angles(h_frags, is_horizontal=True, image_shape=(h, w))
    v_spatial = estimate_spatial_angles(v_frags, is_horizontal=False, image_shape=(h, w))

    return GridGeometry(
        h_angle=h_angle,
        v_angle=v_angle,
        h_period=h_period,
        v_period=v_period,
        h_fragments=h_frags,
        v_fragments=v_frags,
        spatial_angles={
            "horizontal": h_spatial,
            "vertical": v_spatial,
        },
    )
