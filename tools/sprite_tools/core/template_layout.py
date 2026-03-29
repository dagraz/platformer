"""Compute cell positions, margins, and registration marks for a printable
sprite-sheet template.

All coordinates are in pixels at the target DPI.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field


# Paper sizes in inches
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "letter": (8.5, 11.0),
    "a4": (8.267, 11.693),
}

# Margin from page edge to grid area, in inches
PAGE_MARGIN_IN = 0.75

# Gutter between cells, in inches
CELL_GUTTER_IN = 0.2

# Space above each row for label text, in inches
LABEL_HEIGHT_IN = 0.35

# Registration mark size, in points
REG_MARK_SIZE_PT = 10

# Registration mark inset from grid area edge, in points
REG_MARK_INSET_PT = 4


@dataclass
class CellSpec:
    row: int
    col: int
    x: int
    y: int
    width: int
    height: int


@dataclass
class TemplateMeta:
    dpi: int
    paper_width_px: int
    paper_height_px: int
    border_thickness_px: int
    registration_marks: list[dict[str, int]]  # [{"x": ..., "y": ...}, ...]
    rows: list[str]
    cols: int
    cell_width_px: int
    cell_height_px: int
    label_positions: list[dict[str, int | str]]  # [{"x", "y", "label"}, ...]
    cells: list[dict[str, int]]  # [{"row", "col", "x", "y", "width", "height"}, ...]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _inches_to_px(inches: float, dpi: int) -> int:
    return round(inches * dpi)


def _pt_to_px(pt: float, dpi: int) -> int:
    """Convert points (1/72 inch) to pixels at the given DPI."""
    return max(1, round(pt * dpi / 72))


def compute_layout(
    rows: list[str],
    cols: int,
    cell_width_squares: int,
    cell_height_squares: int,
    dpi: int,
    paper: str,
    border_width_pt: float,
) -> TemplateMeta:
    """Compute the full template layout.

    Cell dimensions in the template are scaled so the drawable interior
    (inside the border) maps to cell_width_squares x cell_height_squares
    at a comfortable drawing size.  The actual pixel size is determined
    by fitting the grid onto the page.

    Parameters
    ----------
    rows : list[str]
        State labels (one per row), e.g. ["idle", "walk", "jump", "fall", "climb"].
    cols : int
        Number of columns.
    cell_width_squares, cell_height_squares : int
        Logical cell size (e.g. 4x8 for character sprites).
    dpi : int
        Output resolution.
    paper : str
        Paper size key ("letter" or "a4").
    border_width_pt : float
        Border stroke width in points.
    """
    if paper not in PAPER_SIZES:
        raise ValueError(f"Unknown paper size {paper!r}. Choose from: {list(PAPER_SIZES)}")

    paper_w_in, paper_h_in = PAPER_SIZES[paper]
    paper_w_px = _inches_to_px(paper_w_in, dpi)
    paper_h_px = _inches_to_px(paper_h_in, dpi)
    border_px = _pt_to_px(border_width_pt, dpi)

    margin_px = _inches_to_px(PAGE_MARGIN_IN, dpi)
    gutter_px = _inches_to_px(CELL_GUTTER_IN, dpi)
    label_h_px = _inches_to_px(LABEL_HEIGHT_IN, dpi)

    # Available area inside margins
    avail_w = paper_w_px - 2 * margin_px
    avail_h = paper_h_px - 2 * margin_px

    # Compute cell pixel size from available space.
    # Horizontal: cols * cell_w + (cols - 1) * gutter <= avail_w
    # Vertical:   n_rows * (label_h + cell_h) + (n_rows - 1) * gutter <= avail_h
    n_rows = len(rows)
    cell_aspect = cell_width_squares / cell_height_squares

    # Max cell width from horizontal constraint
    max_cell_w = (avail_w - (cols - 1) * gutter_px) / cols

    # Max cell height from vertical constraint
    max_cell_h = (avail_h - n_rows * label_h_px - (n_rows - 1) * gutter_px) / n_rows

    # Pick the smaller constraint, respecting aspect ratio
    if max_cell_w / cell_aspect <= max_cell_h:
        cell_w = int(max_cell_w)
        cell_h = int(cell_w / cell_aspect)
    else:
        cell_h = int(max_cell_h)
        cell_w = int(cell_h * cell_aspect)

    # Total grid dimensions
    grid_w = cols * cell_w + (cols - 1) * gutter_px
    grid_h = n_rows * (label_h_px + cell_h) + (n_rows - 1) * gutter_px

    # Center grid on page
    grid_x0 = (paper_w_px - grid_w) // 2
    grid_y0 = (paper_h_px - grid_h) // 2

    # Build cell specs and label positions
    cells: list[dict[str, int]] = []
    label_positions: list[dict[str, int | str]] = []

    for r_idx, label in enumerate(rows):
        # Top of this row's label area
        row_top = grid_y0 + r_idx * (label_h_px + cell_h + gutter_px)
        label_y = row_top + label_h_px - _pt_to_px(4, dpi)  # baseline offset
        cell_top = row_top + label_h_px

        label_positions.append({
            "x": grid_x0,
            "y": label_y,
            "label": label.upper(),
        })

        for c_idx in range(cols):
            cell_x = grid_x0 + c_idx * (cell_w + gutter_px)
            cells.append({
                "row": r_idx,
                "col": c_idx,
                "x": cell_x,
                "y": cell_top,
                "width": cell_w,
                "height": cell_h,
            })

    # Registration marks at corners of the grid area
    reg_size = _pt_to_px(REG_MARK_SIZE_PT, dpi)
    reg_inset = _pt_to_px(REG_MARK_INSET_PT, dpi)
    reg_marks = [
        {"x": grid_x0 - reg_inset - reg_size, "y": grid_y0 - reg_inset - reg_size},           # TL
        {"x": grid_x0 + grid_w + reg_inset, "y": grid_y0 - reg_inset - reg_size},              # TR
        {"x": grid_x0 - reg_inset - reg_size, "y": grid_y0 + grid_h + reg_inset},              # BL
        {"x": grid_x0 + grid_w + reg_inset, "y": grid_y0 + grid_h + reg_inset},                # BR
    ]

    return TemplateMeta(
        dpi=dpi,
        paper_width_px=paper_w_px,
        paper_height_px=paper_h_px,
        border_thickness_px=border_px,
        registration_marks=reg_marks,
        rows=rows,
        cols=cols,
        cell_width_px=cell_w,
        cell_height_px=cell_h,
        label_positions=label_positions,
        cells=cells,
    )
