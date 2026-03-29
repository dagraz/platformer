"""sprite-extract: Extract individual cell images from a corrected scan.

Reads a grid.json (from sprite-grid-detect) and the corrected image,
crops each occupied cell, names them by state and frame index, and
writes PNGs plus a cells.json manifest.
"""

import argparse
import json
import os
import sys

from sprite_tools.util.image_io import load_image, save_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-extract",
        description="Extract individual cell images using a grid definition.",
    )
    parser.add_argument(
        "-i", "--input", default="corrected.png",
        help="Path to corrected image",
    )
    parser.add_argument(
        "-g", "--grid", default="grid.json",
        help="Path to grid definition",
    )
    parser.add_argument(
        "--output-dir", default="cells/",
        help="Directory for extracted cell PNGs",
    )
    parser.add_argument(
        "--output-meta", default="cells.json",
        help="Path for metadata JSON",
    )
    parser.add_argument(
        "--rows", required=True,
        help="Comma-separated row-to-state mapping (e.g. idle,walk,jump,fall,climb)",
    )
    parser.add_argument(
        "--skip-empty", action="store_true", default=True,
        help="Skip unoccupied cells (default: true)",
    )
    parser.add_argument(
        "--padding", type=int, default=0,
        help="Pixels to inset from cell boundary (trims grid lines at edges)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load grid definition
    with open(args.grid) as f:
        grid = json.load(f)

    # Load image
    image = load_image(args.input)
    img_h, img_w = image.shape[:2]
    print(f"Loaded image: {img_w}x{img_h}")

    # Parse row-to-state mapping
    state_names = [s.strip() for s in args.rows.split(",")]
    print(f"States: {state_names}")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Process cells
    cells = grid["cells"]
    n_rows = max(c["row"] for c in cells) + 1 if cells else 0

    if len(state_names) < n_rows:
        print(f"Warning: {n_rows} rows in grid but only"
              f" {len(state_names)} state names provided."
              f" Extra rows will use row index as name.")

    # Group occupied cells by row, sorted by column
    rows: dict[int, list[dict]] = {}
    for cell in cells:
        if args.skip_empty and not cell["occupied"]:
            continue
        row = cell["row"]
        rows.setdefault(row, []).append(cell)
    for row in rows:
        rows[row].sort(key=lambda c: c["col"])

    # Extract and save
    pad = args.padding
    extracted: list[dict] = []

    for row_idx in sorted(rows.keys()):
        state = state_names[row_idx] if row_idx < len(state_names) else str(row_idx)
        row_cells = rows[row_idx]

        for frame_idx, cell in enumerate(row_cells):
            # Compute crop region with padding inset
            x0 = cell["x"] + pad
            y0 = cell["y"] + pad
            x1 = cell["x"] + cell["width"] - pad
            y1 = cell["y"] + cell["height"] - pad

            # Clamp to image bounds
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(img_w, x1)
            y1 = min(img_h, y1)

            if x1 <= x0 or y1 <= y0:
                print(f"  Warning: skipping {state}_{frame_idx}"
                      f" — empty crop after padding")
                continue

            crop = image[y0:y1, x0:x1]

            filename = f"{state}_{frame_idx}.png"
            filepath = os.path.join(args.output_dir, filename)
            save_image(crop, filepath)

            extracted.append({
                "state": state,
                "frame": frame_idx,
                "filename": filename,
                "row": cell["row"],
                "col": cell["col"],
                "x": x0,
                "y": y0,
                "width": x1 - x0,
                "height": y1 - y0,
            })

            print(f"  {filename}: {x1-x0}x{y1-y0}px"
                  f" from row={cell['row']} col={cell['col']}")

    # Write metadata
    meta = {
        "source": os.path.basename(args.input),
        "grid": os.path.basename(args.grid),
        "padding": pad,
        "states": state_names[:n_rows],
        "cells": extracted,
    }

    with open(args.output_meta, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nExtracted {len(extracted)} cells to {args.output_dir}")
    print(f"Metadata saved to {args.output_meta}")


if __name__ == "__main__":
    main()
