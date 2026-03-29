"""CLI: Generate a printable sprite-sheet template PDF.

Produces a PDF with thick black bordered cells, pre-printed row labels,
and registration marks at the corners.  A companion template-meta.json
file records cell positions for the detection pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from sprite_tools.core.template_layout import compute_layout

# Named presets: (rows, cols, cell_width_squares, cell_height_squares)
PRESETS: dict[str, tuple[list[str], int, int, int]] = {
    "player": (
        ["idle", "walk", "jump", "fall", "climb"],
        7, 4, 8,
    ),
    "npc": (
        ["idle", "walk", "talk", "emote"],
        7, 4, 8,
    ),
    "terrain": (
        ["grass", "stone", "dirt", "water", "wood", "special"],
        8, 4, 4,
    ),
}


def render_template(meta) -> Image.Image:
    """Render the template as a white raster image with borders, labels,
    and registration marks drawn in black."""

    img = Image.new("L", (meta.paper_width_px, meta.paper_height_px), 255)
    draw = ImageDraw.Draw(img)
    bw = meta.border_thickness_px

    # --- Registration marks (solid black squares) ---
    for mark in meta.registration_marks:
        reg_size = round(10 * meta.dpi / 72)  # 10pt square
        draw.rectangle(
            [mark["x"], mark["y"], mark["x"] + reg_size, mark["y"] + reg_size],
            fill=0,
        )

    # --- Row labels ---
    # Try to get a reasonable font size
    label_font_size = max(12, round(14 * meta.dpi / 72))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", label_font_size)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", label_font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    for lp in meta.label_positions:
        draw.text((lp["x"], lp["y"] - label_font_size), lp["label"], fill=0, font=font)

    # --- Cell borders (thick black rectangles) ---
    for cell in meta.cells:
        x, y, w, h = cell["x"], cell["y"], cell["width"], cell["height"]
        # Draw the border as a filled rectangle minus the interior
        # Outer edge
        draw.rectangle([x, y, x + w, y + h], fill=0)
        # White interior (inset by border thickness)
        draw.rectangle(
            [x + bw, y + bw, x + w - bw, y + h - bw],
            fill=255,
        )

    return img


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="sprite-template",
        description="Generate a printable sprite-sheet template PDF",
    )
    preset_help = ", ".join(
        f"{name} ({','.join(p[0])} / {p[2]}x{p[3]})"
        for name, p in PRESETS.items()
    )
    parser.add_argument("--preset", default=None, choices=list(PRESETS),
                        help=f"Named preset for rows, cols, and cell size. "
                             f"Available: {preset_help}. "
                             f"Explicit --rows/--cols/--cell-width/--cell-height override preset values.")
    parser.add_argument("-o", "--output", default="template.pdf",
                        help="Output PDF path (default: template.pdf)")
    parser.add_argument("--meta", default="template-meta.json",
                        help="Output metadata JSON path (default: template-meta.json)")
    parser.add_argument("--rows", default=None,
                        help="Comma-separated row labels (default: from preset or idle,walk,jump,fall,climb)")
    parser.add_argument("--cols", type=int, default=None,
                        help="Number of columns (default: from preset or 7)")
    parser.add_argument("--cell-width", type=int, default=None,
                        help="Cell width in grid squares (default: from preset or 4)")
    parser.add_argument("--cell-height", type=int, default=None,
                        help="Cell height in grid squares (default: from preset or 8)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="Output resolution (default: 300)")
    parser.add_argument("--paper", default="letter", choices=["letter", "a4"],
                        help="Paper size (default: letter)")
    parser.add_argument("--border-width", type=float, default=3.0,
                        help="Border thickness in points (default: 3)")

    args = parser.parse_args(argv)

    # Apply preset defaults, then let explicit flags override
    preset_rows, preset_cols, preset_cw, preset_ch = PRESETS.get(
        args.preset or "player", PRESETS["player"]
    )
    rows = [r.strip() for r in args.rows.split(",")] if args.rows else preset_rows
    cols = args.cols if args.cols is not None else preset_cols
    cell_width = args.cell_width if args.cell_width is not None else preset_cw
    cell_height = args.cell_height if args.cell_height is not None else preset_ch

    meta = compute_layout(
        rows=rows,
        cols=cols,
        cell_width_squares=cell_width,
        cell_height_squares=cell_height,
        dpi=args.dpi,
        paper=args.paper,
        border_width_pt=args.border_width,
    )

    # Render and save
    img = render_template(meta)

    output_path = Path(args.output)
    if output_path.suffix.lower() == ".pdf":
        img.save(str(output_path), "PDF", resolution=args.dpi)
    else:
        img.save(str(output_path))

    meta_path = Path(args.meta)
    meta_path.write_text(meta.to_json())

    print(f"Template written to {output_path}")
    print(f"Metadata written to {meta_path}")
    print(f"  {len(rows)} rows x {cols} cols = {len(meta.cells)} cells")
    print(f"  Cell size: {meta.cell_width_px} x {meta.cell_height_px} px at {args.dpi} DPI")
    print(f"  Border: {meta.border_thickness_px} px")


if __name__ == "__main__":
    main()
