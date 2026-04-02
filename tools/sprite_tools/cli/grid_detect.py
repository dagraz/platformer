"""sprite-grid-detect: Detect graph paper grid structure from a scan or photo.

Pipeline:
  1. Load image
  2. (Optional) Geometric correction — rotation or perspective
  3. Detect fine grid spacing via autocorrelation
  4. Find cells — via template scaling or morphological detection
  5. Classify occupancy
  6. Write grid.json + optional corrected image + debug image

When --detect-borders is used, the pipeline switches to border-based
detection for printed template scans (Phase B).
"""

import argparse
import json
import os

import cv2
import numpy as np

from sprite_tools.core.correction import correct_image
from sprite_tools.core.border_detect import detect_cells_from_borders
from sprite_tools.core.grid import (
    Cell,
    classify_occupancy,
    detect_fine_grid_spacing,
    find_cells,
    find_cells_from_template,
    to_grid_json,
)
from sprite_tools.util.debug import draw_rects, save_side_by_side
from sprite_tools.util.image_io import load_image, save_image, to_grayscale


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-grid-detect",
        description="Detect graph paper grid structure from a scan or photo.",
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Path to scan/photo image"
    )
    parser.add_argument(
        "-o", "--output", default="grid.json",
        help="Path for output JSON (default: grid.json)",
    )
    parser.add_argument(
        "--template", default=None,
        help="Path to a grid.json from the blank template sheet. "
             "When provided, scales the template grid to match the "
             "current image instead of detecting cells from scratch.",
    )
    parser.add_argument(
        "--debug-image", default=None,
        help="Path to write annotated debug image",
    )
    parser.add_argument(
        "--correct", default="auto",
        choices=["auto", "rotation", "perspective", "none"],
        help="Correction mode (default: auto)",
    )
    parser.add_argument(
        "--corrected-image", default=None,
        help="Path to save the corrected image (default: not saved)",
    )
    parser.add_argument(
        "--max-rotation", type=float, default=15.0,
        help="Maximum rotation angle in degrees (default: 15.0)",
    )
    parser.add_argument(
        "--min-line-length", type=float, default=0.5,
        help="Minimum line length as fraction of image dimension (default: 0.5)",
    )
    parser.add_argument(
        "--detect-borders", action="store_true",
        help="Use border-based detection for printed template scans",
    )
    parser.add_argument(
        "--template-meta", default=None,
        help="Path to template-meta.json (from sprite-template). "
             "Provides expected cell positions and registration mark locations.",
    )
    parser.add_argument(
        "--variance-threshold", type=float, default=None,
        help="Pixel variance threshold for occupancy detection. "
             "Lower values detect lighter artwork (default: 15 for borders, auto for grid).",
    )
    return parser


def _run_border_detection(args, image: np.ndarray) -> None:
    """Border-based detection path for printed template scans."""
    corrected, cells, info = detect_cells_from_borders(
        image, meta_path=args.template_meta,
        variance_threshold=args.variance_threshold,
    )
    h, w = corrected.shape[:2]

    if args.corrected_image:
        save_image(corrected, args.corrected_image)
        print(f"Corrected image saved to {args.corrected_image}")

    n_rows = info["rowCount"]
    n_cols = info["colCount"]
    occupied = [c for c in cells if c.occupied]
    print(f"Detection: borders (border={info['borderThicknessPx']}px)")
    print(f"Cells: {n_rows} rows x {n_cols} cols = {len(cells)} cells")
    print(f"Occupied: {len(occupied)} cells")

    for r in range(n_rows):
        row_occupied = [c.col for c in occupied if c.row == r]
        if row_occupied:
            print(f"  Row {r}: {len(row_occupied)} occupied {row_occupied}")
        else:
            print(f"  Row {r}: 0 occupied")

    # Build grid.json
    corrected_image_path = args.corrected_image or ""
    grid_json = {
        "source": os.path.basename(args.input),
        "correctedImage": os.path.basename(corrected_image_path) if corrected_image_path else "",
        "correction": {
            "type": "registration_marks" if args.template_meta else "none",
        },
        "detection": info["detection"],
        "borderThicknessPx": info["borderThicknessPx"],
        "imageWidth": w,
        "imageHeight": h,
        "cells": [
            {
                "row": c.row,
                "col": c.col,
                "x": c.x,
                "y": c.y,
                "width": c.width,
                "height": c.height,
                "occupied": c.occupied,
            }
            for c in cells
        ],
    }

    with open(args.output, "w") as f:
        json.dump(grid_json, f, indent=2)
    print(f"Grid saved to {args.output}")

    # Debug image
    if args.debug_image:
        debug = corrected.copy()
        gray = to_grayscale(corrected)

        overlay = debug.copy()
        for c in cells:
            color = (0, 200, 0) if c.occupied else (180, 180, 180)
            cv2.rectangle(overlay, (c.x, c.y), (c.x + c.width, c.y + c.height),
                          color, cv2.FILLED)
        cv2.addWeighted(overlay, 0.25, debug, 0.75, 0, debug)

        cell_rects = [(c.x, c.y, c.width, c.height) for c in cells]
        cell_colors = [(0, 255, 0) if c.occupied else (128, 128, 128) for c in cells]
        cell_labels = [f"{c.row},{c.col}" for c in cells]
        debug = draw_rects(debug, cell_rects, cell_colors,
                           thickness=2, labels=cell_labels)
        save_side_by_side(debug, corrected, args.debug_image)
        print(f"Debug image saved to {args.debug_image}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- Stage 1: Load ---
    image = load_image(args.input)
    h, w = image.shape[:2]
    print(f"Loaded image: {w}x{h}")

    # --- Border detection path (for printed templates) ---
    if args.detect_borders:
        _run_border_detection(args, image)
        return

    # --- Stage 2: Geometric correction ---
    if args.correct != "none":
        correction = correct_image(
            image,
            correction_type=args.correct,
            max_rotation=args.max_rotation,
        )
        corrected = correction.corrected_image
        ch, cw = corrected.shape[:2]

        print(f"Correction: type={correction.correction_type}"
              f"  rotation={correction.rotation_degrees:.2f}°"
              f"  residual={correction.residual_px:.2f}px"
              f"  output={cw}x{ch}")
    else:
        corrected = image.copy()
        correction = None
        ch, cw = h, w
        print("Correction: skipped")

    if args.corrected_image:
        save_image(corrected, args.corrected_image)
        print(f"Corrected image saved to {args.corrected_image}")

    # --- Stage 3: Detect fine grid spacing ---
    gray = to_grayscale(corrected)
    spacing = detect_fine_grid_spacing(gray)
    print(f"Fine grid spacing: {spacing:.1f}px")

    # --- Stage 4: Find cells ---
    if args.template:
        cells = find_cells_from_template(gray, spacing, args.template)
    else:
        cells = find_cells(gray, spacing)

    # --- Stage 5: Classify occupancy ---
    cells = classify_occupancy(gray, cells, spacing)

    if cells:
        n_rows = max(c.row for c in cells) + 1
        n_cols = max(c.col for c in cells) + 1
    else:
        n_rows = n_cols = 0

    occupied = [c for c in cells if c.occupied]
    print(f"Cells: {n_rows} rows x {n_cols} cols = {len(cells)} cells")
    print(f"Occupied: {len(occupied)} cells")

    for r in range(n_rows):
        row_occupied = [c.col for c in occupied if c.row == r]
        if row_occupied:
            print(f"  Row {r}: {len(row_occupied)} occupied {row_occupied}")
        else:
            print(f"  Row {r}: 0 occupied")

    # --- Stage 6: JSON output ---
    corrected_image_path = args.corrected_image or ""
    grid_json = to_grid_json(
        source=os.path.basename(args.input),
        corrected_image_path=os.path.basename(corrected_image_path) if corrected_image_path else "",
        correction_type=correction.correction_type if correction else "none",
        rotation_degrees=correction.rotation_degrees if correction else 0.0,
        residual_px=correction.residual_px if correction else 0.0,
        image_width=cw,
        image_height=ch,
        fine_grid_spacing=spacing,
        cells=cells,
    )

    with open(args.output, "w") as f:
        json.dump(grid_json, f, indent=2)
    print(f"Grid saved to {args.output}")

    # --- Stage 7: Debug image ---
    if args.debug_image:
        debug = corrected.copy()

        # Draw semi-transparent cell overlays
        overlay = debug.copy()
        for c in cells:
            color = (0, 200, 0) if c.occupied else (180, 180, 180)
            cv2.rectangle(
                overlay,
                (c.x, c.y),
                (c.x + c.width, c.y + c.height),
                color,
                cv2.FILLED,
            )
        cv2.addWeighted(overlay, 0.25, debug, 0.75, 0, debug)

        # Draw cell boundaries
        cell_rects = [(c.x, c.y, c.width, c.height) for c in cells]
        cell_colors = [
            (0, 255, 0) if c.occupied else (128, 128, 128)
            for c in cells
        ]
        cell_labels = [f"{c.row},{c.col}" for c in cells]
        debug = draw_rects(
            debug, cell_rects, cell_colors,
            thickness=2, labels=cell_labels,
        )

        save_side_by_side(debug, corrected, args.debug_image)
        print(f"Debug image saved to {args.debug_image}")


if __name__ == "__main__":
    main()
