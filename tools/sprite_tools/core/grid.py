"""Grid line fragment analysis and precise grid detection.

Phase 2: Detects LSD line fragments and extracts geometric properties
needed for correction — dominant grid angles, rough grid period, and
spatial angle variation (for perspective estimation).

Phase 3 (additions): After geometric correction produces an axis-aligned
image, find_grid_positions() uses projection profiles to locate precise
grid line positions and classify heavy/light line patterns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class GridDetectionResult:
    """Precise grid positions found on a corrected (axis-aligned) image."""

    h_positions: list[float]     # y-coords of horizontal lines
    v_positions: list[float]     # x-coords of vertical lines
    h_period: float
    v_period: float
    h_heavy_indices: list[int]   # indices into h_positions
    v_heavy_indices: list[int]   # indices into v_positions


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


# ---------------------------------------------------------------------------
# Phase 3: Precise grid detection via projection profiles
# ---------------------------------------------------------------------------


def _build_projection_profile(
    gray: np.ndarray,
    axis: int,
    use_edges: bool = False,
) -> np.ndarray:
    """Build a projection profile along an axis.

    axis=1 -> collapse columns -> profile indexed by y (for horizontal lines)
    axis=0 -> collapse rows    -> profile indexed by x (for vertical lines)

    If use_edges=True, uses Sobel gradient magnitude instead of raw intensity,
    which better isolates grid lines in photos with heavy character art.

    Returns profile where grid lines correspond to peaks.
    """
    if use_edges:
        # For H lines (axis=1): horizontal edges = Sobel in y
        # For V lines (axis=0): vertical edges = Sobel in x
        if axis == 1:
            edges = np.abs(cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3))
        else:
            edges = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3))
        return np.mean(edges, axis=axis)
    else:
        profile = np.mean(gray.astype(np.float64), axis=axis)
        return float(np.max(profile)) - profile



def _dominant_period(
    profile: np.ndarray,
    min_period: float,
    max_period: float,
) -> float:
    """Find dominant period via autocorrelation with FFT.

    Searches for the highest local maximum within [min_period, max_period].
    Uses parabolic interpolation for sub-pixel accuracy.
    """
    centered = profile - np.mean(profile)
    n = len(centered)

    # FFT-based autocorrelation
    fft = np.fft.fft(centered, n=2 * n)
    acf = np.fft.ifft(fft * np.conj(fft)).real[:n]
    if acf[0] > 0:
        acf = acf / acf[0]

    # Search for local maxima in valid range
    lo = max(2, int(min_period))
    hi = min(n - 2, int(max_period) + 1)

    if lo >= hi:
        return (min_period + max_period) / 2

    best_idx = -1
    best_val = -1.0
    for i in range(lo, hi):
        if acf[i] > acf[i - 1] and acf[i] >= acf[i + 1]:
            if acf[i] > best_val:
                best_val = acf[i]
                best_idx = i

    if best_idx < 0:
        # No local maximum found — fall back to global max in range
        best_idx = lo + int(np.argmax(acf[lo:hi]))

    # Parabolic interpolation
    if 1 <= best_idx < n - 1:
        y0, y1, y2 = acf[best_idx - 1], acf[best_idx], acf[best_idx + 1]
        denom = 2 * (2 * y1 - y0 - y2)
        if abs(denom) > 1e-10:
            offset = (y0 - y2) / denom
            return best_idx + offset

    return float(best_idx)


def _find_peak_positions(
    profile: np.ndarray,
    period: float,
) -> list[float]:
    """Find grid-line positions as peaks in the projection profile.

    Finds all local peaks, picks the longest consistent run at the expected
    period, then extrapolates outward and snaps to local peaks.
    """
    n = len(profile)
    if n < 3:
        return []

    # Find all local peaks (above mean)
    threshold = np.mean(profile)
    peaks: list[int] = []
    for i in range(1, n - 1):
        if profile[i] > profile[i - 1] and profile[i] >= profile[i + 1]:
            if profile[i] > threshold:
                peaks.append(i)

    if len(peaks) < 2:
        return [float(p) for p in peaks]

    # Find longest consistent run
    tolerance = 0.15 * period
    best_run_start = 0
    best_run_len = 1
    run_start = 0
    run_len = 1

    for i in range(1, len(peaks)):
        gap = peaks[i] - peaks[i - 1]
        # Allow gap to be ~1x or ~2x period (missing line)
        ratio = gap / period
        if abs(ratio - round(ratio)) * period <= tolerance and 0.5 < ratio < 2.5:
            run_len += 1
        else:
            if run_len > best_run_len:
                best_run_len = run_len
                best_run_start = run_start
            run_start = i
            run_len = 1

    if run_len > best_run_len:
        best_run_len = run_len
        best_run_start = run_start

    seed_peaks = peaks[best_run_start:best_run_start + best_run_len]

    # Build refined positions from the seed
    positions = [float(p) for p in seed_peaks]

    def snap_to_peak(target: float) -> float:
        """Snap target to nearest peak in profile within tolerance."""
        lo_i = max(0, int(target - tolerance))
        hi_i = min(n - 1, int(target + tolerance))
        if lo_i >= hi_i:
            return target
        window = profile[lo_i:hi_i + 1]
        local_peak = lo_i + int(np.argmax(window))
        if profile[local_peak] > threshold * 0.5:
            return float(local_peak)
        return target

    # Extrapolate backward
    pos = positions[0]
    while True:
        target = pos - period
        if target < 0:
            break
        snapped = snap_to_peak(target)
        if snapped < 0:
            break
        positions.insert(0, snapped)
        pos = snapped

    # Extrapolate forward
    pos = positions[-1]
    while True:
        target = pos + period
        if target >= n:
            break
        snapped = snap_to_peak(target)
        if snapped >= n:
            break
        positions.append(snapped)
        pos = snapped

    return positions


def _classify_heavy_lines(
    positions: list[float],
    profile: np.ndarray,
    period: float,
) -> list[int]:
    """Detect heavy (bold) grid lines occurring at regular multiples.

    Tries multiples 2-8, checks if every Nth line has consistently
    higher amplitude. Returns indices of heavy lines, or empty list.
    """
    if len(positions) < 4:
        return []

    # Measure amplitude at each position
    amplitudes = []
    for p in positions:
        idx = int(round(p))
        idx = max(0, min(len(profile) - 1, idx))
        amplitudes.append(float(profile[idx]))

    amplitudes = np.array(amplitudes)

    best_multiple = 0
    best_offset = 0
    best_ratio = 0.0

    for mult in range(2, 9):
        if mult >= len(positions):
            break

        # Try all phase offsets — heavy lines may not start at index 0
        for offset in range(mult):
            heavy_amps = []
            light_amps = []
            for i, amp in enumerate(amplitudes):
                if i % mult == offset:
                    heavy_amps.append(amp)
                else:
                    light_amps.append(amp)

            if not heavy_amps or not light_amps:
                continue

            heavy_mean = float(np.mean(heavy_amps))
            light_mean = float(np.mean(light_amps))
            if light_mean > 0:
                ratio = heavy_mean / light_mean
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_multiple = mult
                    best_offset = offset

    if best_ratio > 1.3 and best_multiple > 0:
        return [i for i in range(len(positions)) if i % best_multiple == best_offset]

    return []


def _acf_peak_score(profile: np.ndarray, min_lag: int, max_lag: int) -> float:
    """Score a profile's periodicity by its strongest ACF peak in [min_lag, max_lag]."""
    centered = profile - np.mean(profile)
    n = len(centered)
    fft = np.fft.fft(centered, n=2 * n)
    acf = np.fft.ifft(fft * np.conj(fft)).real[:n]
    if acf[0] > 0:
        acf = acf / acf[0]

    best = 0.0
    for j in range(min_lag, min(max_lag, n - 1)):
        if acf[j] > acf[j - 1] and acf[j] >= acf[j + 1] and acf[j] > best:
            best = float(acf[j])
    return best


def _best_strip_profile(
    gray: np.ndarray,
    axis: int,
    period_hint: float,
    n_strips: int = 5,
) -> np.ndarray:
    """Select the projection profile strip with strongest periodicity.

    Divides the image into strips perpendicular to the target lines,
    builds a projection profile per strip, scores each by autocorrelation
    peak strength near the expected period, and returns the best one.
    This avoids character-art contamination since some strips will be
    in empty grid areas.

    Also tries edge-enhanced profiles and picks the overall best.
    """
    h, w = gray.shape[:2]
    # Tight scoring range to avoid sub-harmonics pulling the selection
    score_min = max(5, int(0.7 * period_hint))
    score_max = int(1.5 * period_hint) + 1

    best_profile = None
    best_score = -1.0

    # For H lines (axis=1): strips divide along x (columns)
    # For V lines (axis=0): strips divide along y (rows)
    strip_dim = w if axis == 1 else h
    strip_size = strip_dim // n_strips

    for use_edges in [False, True]:
        # Full-image profile
        full = _build_projection_profile(gray, axis, use_edges=use_edges)
        score = _acf_peak_score(full, score_min, score_max)
        if score > best_score:
            best_score = score
            best_profile = full

        # Per-strip profiles
        for s in range(n_strips):
            start = s * strip_size
            end = start + strip_size if s < n_strips - 1 else strip_dim

            if axis == 1:
                strip = gray[:, start:end]
            else:
                strip = gray[start:end, :]

            if strip.size == 0:
                continue

            profile = _build_projection_profile(strip, axis, use_edges=use_edges)
            score = _acf_peak_score(profile, score_min, score_max)
            if score > best_score:
                best_score = score
                best_profile = profile

    return best_profile


def find_grid_positions(
    corrected_image: np.ndarray,
    h_period_hint: float,
    v_period_hint: float,
    expected_rows: int = 58,
    expected_cols: int = 36,
) -> GridDetectionResult:
    """Find precise grid line positions on a corrected axis-aligned image.

    Uses projection profiles (intensity sums along rows/columns) to detect
    grid lines as peaks. The period hints from Phase 2 guide the search.

    Args:
        corrected_image: BGR image after geometric correction.
        h_period_hint: Approximate vertical spacing between H lines (pixels).
        v_period_hint: Approximate horizontal spacing between V lines (pixels).
        expected_rows: Expected number of horizontal grid lines.
        expected_cols: Expected number of vertical grid lines.

    Returns:
        GridDetectionResult with positions, periods, and heavy line indices.
    """
    gray = cv2.cvtColor(corrected_image, cv2.COLOR_BGR2GRAY)

    # Horizontal lines (profile along y-axis, collapse columns)
    h_profile = _best_strip_profile(gray, axis=1, period_hint=h_period_hint)
    h_period = _dominant_period(
        h_profile,
        min_period=0.5 * h_period_hint,
        max_period=2.0 * h_period_hint,
    )
    h_positions = _find_peak_positions(h_profile, h_period)
    h_heavy = _classify_heavy_lines(h_positions, h_profile, h_period)

    # Vertical lines (profile along x-axis, collapse rows)
    v_profile = _best_strip_profile(gray, axis=0, period_hint=v_period_hint)
    v_period = _dominant_period(
        v_profile,
        min_period=0.5 * v_period_hint,
        max_period=2.0 * v_period_hint,
    )
    v_positions = _find_peak_positions(v_profile, v_period)
    v_heavy = _classify_heavy_lines(v_positions, v_profile, v_period)

    return GridDetectionResult(
        h_positions=h_positions,
        v_positions=v_positions,
        h_period=h_period,
        v_period=v_period,
        h_heavy_indices=h_heavy,
        v_heavy_indices=v_heavy,
    )
