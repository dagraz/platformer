"""Grid detection via morphological analysis and grid extrapolation.

Detects the fine grid structure on graph paper by:
  1. Autocorrelation-based fine grid spacing detection
  2. Morphological closing to find blank cells (regions with no grid lines)
  3. Grid pattern extrapolation from detected blank cells
  4. Variance-based occupancy classification

Supports two modes:
  - **Template mode** (--template): Scale a known grid layout from a blank
    sheet to match the current image's spacing, then align using detected
    blank cells as anchors. Most reliable.
  - **Auto mode** (no template): Detect blank cells morphologically and
    extrapolate the regular grid pattern. Works when enough blank cells exist.

The graph paper has a known structure: uniform fine grid lines covering the
background, with cells defined as blank rectangles where grid lines have been
removed. Cells are arranged in a regular grid with 1-square grid strips
between them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    """A drawing cell in the sprite sheet grid."""

    row: int
    col: int
    x: int        # top-left x in corrected image
    y: int        # top-left y in corrected image
    width: int
    height: int
    occupied: bool


# ---------------------------------------------------------------------------
# Phase 2: Fine grid spacing detection
# ---------------------------------------------------------------------------


def compute_density_profile(image_gray: np.ndarray, axis: int) -> np.ndarray:
    """Project pixel intensities along an axis to create a 1D density profile.

    axis=0 → sum each column → horizontal profile (detects vertical lines)
    axis=1 → sum each row → vertical profile (detects horizontal lines)

    Returns 1D array where grid lines correspond to peaks (inverted so
    dark lines on light paper become peaks).
    """
    profile = np.mean(image_gray.astype(np.float64), axis=axis)
    # Invert: grid lines are dark on light paper, make them peaks
    return float(np.max(profile)) - profile


def _autocorrelate(signal: np.ndarray) -> np.ndarray:
    """FFT-based autocorrelation, normalized so lag-0 = 1.0."""
    centered = signal - np.mean(signal)
    n = len(centered)
    fft = np.fft.fft(centered, n=2 * n)
    acf = np.fft.ifft(fft * np.conj(fft)).real[:n]
    if acf[0] > 0:
        acf = acf / acf[0]
    return acf


def _find_acf_peak(acf: np.ndarray, min_lag: int, max_lag: int) -> float:
    """Find the strongest local maximum in the ACF within [min_lag, max_lag].

    Uses parabolic interpolation for sub-pixel accuracy.
    """
    n = len(acf)
    lo = max(2, min_lag)
    hi = min(n - 2, max_lag)

    if lo >= hi:
        return float((min_lag + max_lag) // 2)

    best_idx = -1
    best_val = -1.0
    for i in range(lo, hi + 1):
        if acf[i] > acf[i - 1] and acf[i] >= acf[i + 1]:
            if acf[i] > best_val:
                best_val = acf[i]
                best_idx = i

    if best_idx < 0:
        # No local maximum — fallback to global max in range
        best_idx = lo + int(np.argmax(acf[lo:hi + 1]))

    # Parabolic interpolation for sub-pixel accuracy
    if 1 <= best_idx < n - 1:
        y0, y1, y2 = acf[best_idx - 1], acf[best_idx], acf[best_idx + 1]
        denom = 2 * (2 * y1 - y0 - y2)
        if abs(denom) > 1e-10:
            offset = (y0 - y2) / denom
            return best_idx + offset

    return float(best_idx)


def detect_fine_grid_spacing(image_gray: np.ndarray) -> float:
    """Find the fundamental fine grid line spacing in pixels.

    Applies Gaussian blur to merge double-edge peaks from grid line edges,
    then runs autocorrelation on a central strip to find the dominant period.
    Both axes should agree (square grid). Returns the average spacing.
    """
    h, w = image_gray.shape[:2]

    # Use central strip to avoid edge effects
    y0, y1 = h // 4, 3 * h // 4
    x0, x1 = w // 4, 3 * w // 4
    strip = image_gray[y0:y1, x0:x1]

    # Blur to merge double-edge peaks from grid line edges
    blurred_v = cv2.GaussianBlur(strip, (1, 7), 2.0)  # blur along y
    blurred_h = cv2.GaussianBlur(strip, (7, 1), 2.0)  # blur along x

    # Vertical profile (sum each row → detects horizontal lines)
    v_profile = compute_density_profile(blurred_v, axis=1)
    v_acf = _autocorrelate(v_profile)

    # Horizontal profile (sum each column → detects vertical lines)
    h_profile = compute_density_profile(blurred_h, axis=0)
    h_acf = _autocorrelate(h_profile)

    # Search range: grid spacing is typically 15-100 pixels
    min_lag = 15
    max_lag = min(200, len(v_acf) // 4)

    v_spacing = _find_acf_peak(v_acf, min_lag, max_lag)
    h_spacing = _find_acf_peak(h_acf, min_lag, max_lag)

    # Check agreement
    if min(v_spacing, h_spacing) > 0:
        ratio = max(v_spacing, h_spacing) / min(v_spacing, h_spacing)
        if ratio > 1.05:
            print(f"  Warning: H/V grid spacing disagree:"
                  f" H={h_spacing:.1f}px V={v_spacing:.1f}px")
            if ratio > 1.5:
                # One axis likely detected a harmonic (2×, 3× the true spacing).
                # Prefer the smaller value — it's the fundamental frequency.
                smaller = min(h_spacing, v_spacing)
                print(f"  Using smaller value ({smaller:.1f}px)"
                      f" — larger is likely a harmonic")
                return smaller

    return (h_spacing + v_spacing) / 2


# ---------------------------------------------------------------------------
# Phase 3: Cell finding via morphological analysis + extrapolation
# ---------------------------------------------------------------------------


def _find_blank_regions(
    image_gray: np.ndarray,
    spacing: float,
) -> list[tuple[int, int, int, int]]:
    """Find blank rectangular regions using morphological closing.

    Inverts the image (so grid lines are white), applies directional
    morphological closing to connect grid line fragments, then finds
    connected components of the remaining blank areas.

    Returns list of (x, y, width, height) for cell-sized blank regions,
    sorted by (y, x).
    """
    inv = 255 - image_gray

    # Morphological closing with directional kernels.
    # Kernel length = 1.5× spacing bridges gaps between adjacent grid lines.
    klen = max(3, int(spacing * 1.5))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (klen, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, klen))

    closed_h = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel_h)
    closed_v = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel_v)
    closed = np.maximum(closed_h, closed_v)

    # Threshold to binary — blank regions have low closed values
    _, binary = cv2.threshold(closed, 15, 255, cv2.THRESH_BINARY)
    blank_mask = 255 - binary

    # Find connected components
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        blank_mask
    )

    # Filter by expected cell size: ~4×8 grid squares
    min_w = spacing * 2.5
    max_w = spacing * 6
    min_h = spacing * 5
    max_h = spacing * 11

    regions = []
    for i in range(1, n_labels):  # skip background (label 0)
        x, y, w, h, area = stats[i]
        if min_w <= w <= max_w and min_h <= h <= max_h:
            regions.append((int(x), int(y), int(w), int(h)))

    regions.sort(key=lambda r: (r[1], r[0]))
    return regions


def _extrapolate_1d(
    detected: list[int],
    pitch: int,
    cell_size: int,
    image_size: int,
) -> list[int]:
    """Extrapolate a 1D regular grid from detected anchor positions.

    Fills gaps between detected positions and extends one pitch beyond the
    detected range in each direction (but not further — the grid doesn't
    necessarily fill the entire image).
    """
    if not detected:
        return []

    anchor = min(detected)
    max_pos = max(detected)

    # Extend one pitch beyond detected range in each direction
    start = anchor - pitch
    end = max_pos + pitch

    positions = []
    p = start
    while p <= end:
        if 0 <= p and p + cell_size <= image_size:
            positions.append(p)
        p += pitch

    return positions


def find_cells(
    image_gray: np.ndarray,
    spacing: float,
) -> list[Cell]:
    """Find all cell positions in the sprite sheet grid.

    Uses morphological analysis to detect blank cells (those without grid
    lines or art), then extrapolates the regular grid pattern to find all
    cell positions — including cells that contain character art and couldn't
    be found by the morphological detector alone.

    Args:
        image_gray: Grayscale image (corrected).
        spacing: Fine grid spacing in pixels.

    Returns:
        List of Cell objects (not yet classified for occupancy).
    """
    img_h, img_w = image_gray.shape[:2]
    blank_regions = _find_blank_regions(image_gray, spacing)

    if not blank_regions:
        print("  Warning: no blank cell regions detected")
        return []

    # Median cell dimensions from detected blank cells
    cell_w = int(round(float(np.median([r[2] for r in blank_regions]))))
    cell_h = int(round(float(np.median([r[3] for r in blank_regions]))))

    # --- Group blank regions into rows by y-position ---
    row_groups: list[list[tuple[int, int, int, int]]] = []
    for region in blank_regions:
        placed = False
        for group in row_groups:
            if abs(region[1] - group[0][1]) < cell_h * 0.3:
                group.append(region)
                placed = True
                break
        if not placed:
            row_groups.append([region])
    row_groups.sort(key=lambda g: g[0][1])

    # --- Determine column pitch ---
    x_diffs: list[int] = []
    for group in row_groups:
        xs = sorted(r[0] for r in group)
        for i in range(1, len(xs)):
            diff = xs[i] - xs[i - 1]
            if spacing * 3 < diff < spacing * 8:
                x_diffs.append(diff)

    if x_diffs:
        col_pitch = int(round(float(np.median(x_diffs))))
    else:
        col_pitch = cell_w + int(round(spacing))

    # --- Determine row pitch ---
    detected_row_ys = [
        int(round(float(np.median([r[1] for r in g])))) for g in row_groups
    ]

    if len(detected_row_ys) >= 2:
        row_diffs = [
            detected_row_ys[i + 1] - detected_row_ys[i]
            for i in range(len(detected_row_ys) - 1)
        ]
        row_pitch = int(round(float(np.median(row_diffs))))
    else:
        # Fallback: cell height + label space (~3 grid squares)
        row_pitch = cell_h + int(round(spacing * 3))

    print(f"  Blank regions: {len(blank_regions)} detected"
          f" in {len(row_groups)} rows")
    print(f"  Cell size: {cell_w}x{cell_h}px"
          f"  col_pitch={col_pitch}  row_pitch={row_pitch}")

    # --- Extrapolate column positions ---
    all_xs = sorted(set(r[0] for r in blank_regions))
    col_positions = _extrapolate_1d(all_xs, col_pitch, cell_w, img_w)

    # --- Extrapolate row positions ---
    row_positions = _extrapolate_1d(detected_row_ys, row_pitch, cell_h, img_h)

    print(f"  Grid: {len(row_positions)} rows x {len(col_positions)} cols"
          f" = {len(row_positions) * len(col_positions)} cells")

    # --- Build cells ---
    cells: list[Cell] = []
    for row_idx, ry in enumerate(row_positions):
        for col_idx, cx in enumerate(col_positions):
            cells.append(Cell(
                row=row_idx,
                col=col_idx,
                x=cx,
                y=ry,
                width=cell_w,
                height=cell_h,
                occupied=False,
            ))

    return cells


# ---------------------------------------------------------------------------
# Template-based cell finding
# ---------------------------------------------------------------------------


def find_cells_from_template(
    image_gray: np.ndarray,
    spacing: float,
    template_path: str,
) -> list[Cell]:
    """Find cells by scaling a known template grid to match the current image.

    Loads a previously generated grid.json from a blank sheet, scales all
    cell positions by the ratio of current spacing to template spacing, then
    aligns the scaled grid to the image using detected blank cells as anchors.

    Args:
        image_gray: Grayscale corrected image.
        spacing: Fine grid spacing detected on this image.
        template_path: Path to a grid.json generated from the blank template.

    Returns:
        List of Cell objects (not yet classified for occupancy).
    """
    with open(template_path) as f:
        template = json.load(f)

    template_spacing = template["fineGridSpacing"]
    template_cells = template["cells"]

    if not template_cells:
        print("  Warning: template grid.json has no cells")
        return []

    scale = spacing / template_spacing
    print(f"  Template: {len(template_cells)} cells,"
          f" spacing={template_spacing:.1f}px,"
          f" scale={scale:.4f}")

    # Scale template cell positions and dimensions
    scaled: list[dict] = []
    for tc in template_cells:
        scaled.append({
            "row": tc["row"],
            "col": tc["col"],
            "x": tc["x"] * scale,
            "y": tc["y"] * scale,
            "width": tc["width"] * scale,
            "height": tc["height"] * scale,
        })

    # Detect blank cells in the current image for alignment
    blank_regions = _find_blank_regions(image_gray, spacing)
    print(f"  Alignment anchors: {len(blank_regions)} blank regions detected")

    # Find alignment offset: match each detected blank region to the nearest
    # scaled template cell and compute the median translation
    if blank_regions:
        dx_list: list[float] = []
        dy_list: list[float] = []
        for bx, by, bw, bh in blank_regions:
            best_dist = float("inf")
            best_dx = 0.0
            best_dy = 0.0
            for sc in scaled:
                d = abs(bx - sc["x"]) + abs(by - sc["y"])
                if d < best_dist:
                    best_dist = d
                    best_dx = bx - sc["x"]
                    best_dy = by - sc["y"]
            dx_list.append(best_dx)
            dy_list.append(best_dy)

        dx = float(np.median(dx_list))
        dy = float(np.median(dy_list))
        print(f"  Alignment offset: dx={dx:.1f}  dy={dy:.1f}")
    else:
        dx = 0.0
        dy = 0.0
        print("  Warning: no blank regions for alignment, using unshifted grid")

    # Apply offset and build cells
    img_h, img_w = image_gray.shape[:2]
    cells: list[Cell] = []
    for sc in scaled:
        x = int(round(sc["x"] + dx))
        y = int(round(sc["y"] + dy))
        w = int(round(sc["width"]))
        h = int(round(sc["height"]))

        # Skip cells that fall outside the image
        if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
            continue

        cells.append(Cell(
            row=sc["row"],
            col=sc["col"],
            x=x,
            y=y,
            width=w,
            height=h,
            occupied=False,
        ))

    print(f"  Template grid: {len(cells)} cells mapped to image")
    return cells


# ---------------------------------------------------------------------------
# Occupancy classification
# ---------------------------------------------------------------------------


def classify_occupancy(
    image_gray: np.ndarray,
    cells: list[Cell],
    fine_grid_spacing: float,
) -> list[Cell]:
    """Mark cells as occupied or empty based on pixel variance.

    Empty cells are nearly uniform (blank paper). Cells with character art
    have significantly higher variance due to pencil strokes.

    Uses Otsu's method on the distribution of cell standard deviations
    to find the split between empty and occupied cells.
    """
    if not cells:
        return cells

    std_devs: list[float] = []
    for cell in cells:
        patch = image_gray[cell.y:cell.y + cell.height,
                           cell.x:cell.x + cell.width]
        if patch.size > 0:
            std_devs.append(float(np.std(patch)))
        else:
            std_devs.append(0.0)

    arr = np.array(std_devs)
    sorted_vals = np.sort(arr)

    if len(sorted_vals) < 2:
        return cells

    # Absolute floor: cells below this std dev are always empty.
    # Grid-line texture between cells has std ≈ 10-12; character art has
    # std >> 15. This prevents grid-texture regions from being classified
    # as occupied.
    MIN_OCCUPIED_STDDEV = 15.0

    # Find the largest gap between consecutive sorted values
    gaps = np.diff(sorted_vals)
    best_gap_idx = int(np.argmax(gaps))
    threshold = (sorted_vals[best_gap_idx] + sorted_vals[best_gap_idx + 1]) / 2

    # Ensure threshold is at least the minimum
    threshold = max(threshold, MIN_OCCUPIED_STDDEV)

    for i, cell in enumerate(cells):
        cell.occupied = bool(std_devs[i] > threshold)

    return cells


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def to_grid_json(
    source: str,
    corrected_image_path: str,
    correction_type: str,
    rotation_degrees: float,
    residual_px: float,
    image_width: int,
    image_height: int,
    fine_grid_spacing: float,
    cells: list[Cell],
) -> dict:
    """Build the grid.json output dict matching the v4 PRD schema."""
    return {
        "source": source,
        "correctedImage": corrected_image_path,
        "correction": {
            "type": correction_type,
            "rotationDegrees": round(rotation_degrees, 2),
            "residualErrorPx": round(residual_px, 2),
        },
        "imageWidth": image_width,
        "imageHeight": image_height,
        "fineGridSpacing": round(fine_grid_spacing, 1),
        "cells": [
            {
                "row": c.row,
                "col": c.col,
                "x": c.x,
                "y": c.y,
                "width": c.width,
                "height": c.height,
                "occupied": bool(c.occupied),
            }
            for c in cells
        ],
    }
