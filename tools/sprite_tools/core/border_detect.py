"""Border-based cell detection for printed sprite-sheet templates.

Detects thick black rectangular borders via contour detection, then
crops inside them.  Registration marks at grid corners provide deskew
anchors.  This replaces the morphological grid-density approach for
template scans.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class DetectedCell:
    """A cell detected from its border contour."""
    row: int
    col: int
    x: int          # inner x (inset past border)
    y: int          # inner y
    width: int      # inner width
    height: int     # inner height
    occupied: bool


def find_registration_marks(
    gray: np.ndarray,
    expected_size_range: tuple[int, int] = (15, 120),
) -> list[tuple[int, int]]:
    """Find four solid black squares at the grid corners.

    Returns four (cx, cy) center points ordered: TL, TR, BL, BR.
    Raises ValueError if fewer than 4 marks are found.
    """
    h, w = gray.shape[:2]

    # Threshold: registration marks are solid black (near 0)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[int, int, int, int]] = []  # cx, cy, area, idx
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        # Size filter
        if not (expected_size_range[0] <= bw <= expected_size_range[1]):
            continue
        if not (expected_size_range[0] <= bh <= expected_size_range[1]):
            continue
        # Roughly square
        aspect = bw / bh if bh > 0 else 0
        if not (0.6 < aspect < 1.67):
            continue
        # Solid fill: contour area should be close to bounding rect area
        area = cv2.contourArea(cnt)
        rect_area = bw * bh
        if rect_area > 0 and area / rect_area < 0.7:
            continue
        cx = x + bw // 2
        cy = y + bh // 2
        candidates.append((cx, cy, area, len(candidates)))

    if len(candidates) < 4:
        raise ValueError(
            f"Expected 4 registration marks, found {len(candidates)}. "
            "Ensure the template was scanned with marks visible."
        )

    # Pick the four candidates closest to the image corners
    corners = [
        (0, 0),          # TL
        (w, 0),          # TR
        (0, h),          # BL
        (w, h),          # BR
    ]
    selected: list[tuple[int, int]] = []
    used: set[int] = set()
    for corner_x, corner_y in corners:
        best_idx = -1
        best_dist = float("inf")
        for i, (cx, cy, _, _) in enumerate(candidates):
            if i in used:
                continue
            dist = math.hypot(cx - corner_x, cy - corner_y)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        used.add(best_idx)
        selected.append((candidates[best_idx][0], candidates[best_idx][1]))

    return selected


def deskew_from_marks(
    image: np.ndarray,
    detected_corners: list[tuple[int, int]],
    expected_corners: list[dict[str, int]],
    reg_mark_size_px: int,
) -> np.ndarray:
    """Compute perspective transform from detected registration marks to
    their expected positions (from template-meta.json) and warp the image.

    Parameters
    ----------
    image : np.ndarray
        The scanned image (BGR or grayscale).
    detected_corners : list of (cx, cy)
        Detected mark centers, ordered TL, TR, BL, BR.
    expected_corners : list of {"x": int, "y": int}
        Expected mark top-left positions from template metadata.
    reg_mark_size_px : int
        Size of the registration mark in pixels (to compute center from TL).
    """
    half = reg_mark_size_px // 2
    src_pts = np.array(detected_corners, dtype=np.float32)
    dst_pts = np.array(
        [(c["x"] + half, c["y"] + half) for c in expected_corners],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    h_out = max(c["y"] for c in expected_corners) + reg_mark_size_px + 50
    w_out = max(c["x"] for c in expected_corners) + reg_mark_size_px + 50
    warped = cv2.warpPerspective(image, M, (w_out, h_out),
                                  borderMode=cv2.BORDER_CONSTANT,
                                  borderValue=(255, 255, 255) if image.ndim == 3 else 255)
    return warped


def _rects_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int],
                   threshold: float = 0.5) -> bool:
    """Check if two rects overlap significantly (IoU of the smaller > threshold)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    intersection = ix * iy
    smaller_area = min(aw * ah, bw * bh)
    return smaller_area > 0 and intersection / smaller_area > threshold


def find_cell_borders(
    gray: np.ndarray,
    border_thickness_px: int,
    expected_aspect: float = 0.5,
    aspect_tolerance: float = 0.3,
    min_area: int = 1000,
) -> list[tuple[int, int, int, int]]:
    """Find thick black rectangular borders and return inner crop rects.

    Returns list of (x, y, width, height) representing the drawable
    interior of each cell (inset past the border line).
    Sorted top-to-bottom, left-to-right.
    """
    # Threshold: printed black borders are near-zero luminance
    _, binary = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

    # Close small gaps in the border (scanner artifacts)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[int, int, int, int]] = []
    # Collect all areas to compute a size filter: real cells cluster
    # at a consistent size, text fragments are much smaller.
    all_areas = []
    for cnt in contours:
        bw, bh = cv2.boundingRect(cnt)[2:]
        aspect = bw / bh if bh > 0 else 0
        if abs(aspect - expected_aspect) <= aspect_tolerance and bw * bh >= min_area:
            all_areas.append(bw * bh)

    # Use median area to reject contours that are too small (text, noise)
    if all_areas:
        median_area = sorted(all_areas)[len(all_areas) // 2]
        effective_min_area = max(min_area, int(median_area * 0.4))
    else:
        effective_min_area = min_area

    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        area = bw * bh
        if area < effective_min_area:
            continue

        # Aspect ratio filter
        aspect = bw / bh if bh > 0 else 0
        if abs(aspect - expected_aspect) > aspect_tolerance:
            continue

        # Must be a rectangle: approximate polygon should have ~4 vertices
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        if len(approx) < 4 or len(approx) > 6:
            continue

        # Interior should be mostly white — reject solid black blobs
        inner_x = x + border_thickness_px
        inner_y = y + border_thickness_px
        inner_w = bw - 2 * border_thickness_px
        inner_h = bh - 2 * border_thickness_px
        if inner_w <= 0 or inner_h <= 0:
            continue
        roi = gray[inner_y:inner_y + inner_h, inner_x:inner_x + inner_w]
        if roi.size == 0:
            continue
        if roi.mean() < 160:
            continue

        candidates.append((inner_x, inner_y, inner_w, inner_h))

    # Deduplicate overlapping rects — keep the largest one in each cluster
    candidates.sort(key=lambda r: r[2] * r[3], reverse=True)
    rects: list[tuple[int, int, int, int]] = []
    for cand in candidates:
        if not any(_rects_overlap(cand, kept) for kept in rects):
            rects.append(cand)

    rects.sort(key=lambda r: (r[1], r[0]))
    return rects


def assign_grid_positions(
    rects: list[tuple[int, int, int, int]],
    row_tolerance_frac: float = 0.3,
) -> list[tuple[int, int, int, int, int, int]]:
    """Assign row/col indices to detected cell rects.

    Groups rects into rows by y-position proximity, then assigns
    column indices left-to-right within each row.

    Returns list of (row, col, x, y, w, h).
    """
    if not rects:
        return []

    # Cluster by y into rows
    median_h = sorted(r[3] for r in rects)[len(rects) // 2]
    tolerance = median_h * row_tolerance_frac

    rows: list[list[tuple[int, int, int, int]]] = []
    for rect in rects:
        placed = False
        for row_group in rows:
            if abs(rect[1] - row_group[0][1]) < tolerance:
                row_group.append(rect)
                placed = True
                break
        if not placed:
            rows.append([rect])

    # Sort rows by average y, columns by x
    rows.sort(key=lambda grp: sum(r[1] for r in grp) / len(grp))
    result = []
    for r_idx, row_group in enumerate(rows):
        row_group.sort(key=lambda r: r[0])
        for c_idx, (x, y, w, h) in enumerate(row_group):
            result.append((r_idx, c_idx, x, y, w, h))

    return result


def classify_occupancy(
    gray: np.ndarray,
    cells: list[tuple[int, int, int, int, int, int]],
    empty_variance_threshold: float = 15.0,
) -> list[DetectedCell]:
    """Mark cells as occupied or empty based on pixel variance.

    Empty cells have nearly uniform white interiors (low variance).
    Cells with pencil/colored pencil art have higher variance.
    """
    result: list[DetectedCell] = []
    for row, col, x, y, w, h in cells:
        # Sample a margin-inset region to avoid border residue
        margin = max(4, min(w, h) // 10)
        roi = gray[y + margin:y + h - margin, x + margin:x + w - margin]
        if roi.size == 0:
            variance = 0.0
        else:
            variance = float(np.var(roi))
        result.append(DetectedCell(
            row=row, col=col, x=x, y=y, width=w, height=h,
            occupied=variance > empty_variance_threshold,
        ))
    return result


def detect_cells_from_borders(
    image: np.ndarray,
    meta_path: str | Path | None = None,
    border_thickness_px: int | None = None,
    variance_threshold: float | None = None,
) -> tuple[np.ndarray, list[DetectedCell], dict]:
    """Full border-based detection pipeline.

    Parameters
    ----------
    image : np.ndarray
        Scanned image (BGR).
    meta_path : path, optional
        Path to template-meta.json for guided detection.
    border_thickness_px : int, optional
        Override border thickness. Read from meta if available.

    Returns
    -------
    corrected : np.ndarray
        Deskewed image.
    cells : list[DetectedCell]
        Detected cells with row/col and occupancy.
    info : dict
        Extra info for grid.json (detection method, border thickness, etc.).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    meta = None

    if meta_path is not None:
        meta_text = Path(meta_path).read_text()
        meta = json.loads(meta_text)

    # Determine border thickness
    if border_thickness_px is None:
        if meta is not None:
            border_thickness_px = meta["border_thickness_px"]
        else:
            border_thickness_px = 12  # reasonable default for 300 DPI

    corrected = image.copy()

    # Deskew via registration marks if meta is available
    if meta is not None:
        try:
            marks = find_registration_marks(gray)
            reg_size = round(10 * meta["dpi"] / 72)
            corrected = deskew_from_marks(image, marks, meta["registration_marks"], reg_size)
            gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY) if corrected.ndim == 3 else corrected.copy()
        except ValueError:
            # Fall back to no deskew if marks not found
            pass

    # Detect cell borders
    expected_aspect = 0.5  # 1:2 for character cells
    if meta is not None and meta["cell_width_px"] > 0 and meta["cell_height_px"] > 0:
        expected_aspect = meta["cell_width_px"] / meta["cell_height_px"]

    rects = find_cell_borders(gray, border_thickness_px, expected_aspect=expected_aspect)

    if not rects:
        raise ValueError("No cell borders detected. Check that the scan has thick black borders.")

    # Assign grid positions
    positioned = assign_grid_positions(rects)

    # Classify occupancy
    occ_kwargs = {}
    if variance_threshold is not None:
        occ_kwargs["empty_variance_threshold"] = variance_threshold
    cells = classify_occupancy(gray, positioned, **occ_kwargs)

    info = {
        "detection": "borders",
        "borderThicknessPx": border_thickness_px,
        "cellCount": len(cells),
        "rowCount": max(c.row for c in cells) + 1 if cells else 0,
        "colCount": max(c.col for c in cells) + 1 if cells else 0,
    }

    return corrected, cells, info
