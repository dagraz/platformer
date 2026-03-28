"""sprite-grid-detect: Detect graph paper grid structure from a scan or photo.

Pipeline:
  1. Analyze grid geometry (Phase 2 — LSD fragments)
  2. Correct distortion (Phase 3 — rotation or perspective)
  3. Find precise grid positions (Phase 3 — projection profiles)
"""

import argparse

from sprite_tools.core.correction import correct_image
from sprite_tools.core.grid import analyze_grid_geometry, find_grid_positions
from sprite_tools.util.debug import draw_grid, draw_lines, save_side_by_side
from sprite_tools.util.image_io import load_image, save_image


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
        "--debug-image", default=None,
        help="Path to write annotated debug image (side-by-side)",
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
        "--expected-rows", type=int, default=58,
        help="Expected number of horizontal grid lines (default: 58)",
    )
    parser.add_argument(
        "--expected-cols", type=int, default=36,
        help="Expected number of vertical grid lines (default: 36)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # --- Stage 1: Load ---
    image = load_image(args.input)
    h, w = image.shape[:2]
    print(f"Loaded image: {w}x{h}")

    # --- Stage 2: Fragment analysis (Phase 2) ---
    geo = analyze_grid_geometry(image)

    print(f"Fragments: {len(geo.h_fragments)} horizontal, {len(geo.v_fragments)} vertical")
    print(f"Dominant angles: H={geo.h_angle:.2f}° V={geo.v_angle:.2f}°")
    print(f"Grid period: H={geo.h_period:.1f}px V={geo.v_period:.1f}px")

    h_rotation = geo.h_angle if geo.h_angle < 90 else geo.h_angle - 180
    print(f"Rotation estimate: {h_rotation:.2f}°")

    for direction in ["horizontal", "vertical"]:
        spatial = geo.spatial_angles[direction]
        zone_str = ", ".join(
            f"{a:.2f}°" if a == a else "n/a"  # nan check
            for a in spatial["zone_angles"]
        )
        print(f"  {direction.capitalize()} angle by zone: [{zone_str}]"
              f"  range={spatial['angle_range']:.2f}° std={spatial['angle_std']:.2f}°")

    # --- Stage 3: Geometric correction (Phase 3) ---
    correction = correct_image(
        image, geo,
        correction_type=args.correct,
        max_rotation=args.max_rotation,
    )
    corrected = correction.corrected_image
    ch, cw = corrected.shape[:2]

    print(f"Correction: type={correction.correction_type}"
          f"  rotation={correction.rotation_degrees:.2f}°"
          f"  residual={correction.residual_px:.2f}px"
          f"  output={cw}x{ch}")

    if args.corrected_image:
        save_image(corrected, args.corrected_image)
        print(f"Corrected image saved to {args.corrected_image}")

    # --- Stage 4: Grid position finding (Phase 3) ---
    grid = find_grid_positions(
        corrected,
        h_period_hint=geo.h_period,
        v_period_hint=geo.v_period,
        expected_rows=args.expected_rows,
        expected_cols=args.expected_cols,
    )

    print(f"Grid lines: {len(grid.h_positions)} horizontal, {len(grid.v_positions)} vertical")
    print(f"Refined period: H={grid.h_period:.1f}px V={grid.v_period:.1f}px")
    if grid.h_heavy_indices and len(grid.h_heavy_indices) > 1:
        h_stride = grid.h_heavy_indices[1] - grid.h_heavy_indices[0]
        print(f"Heavy H lines: {len(grid.h_heavy_indices)} (every {h_stride} lines)")
    if grid.v_heavy_indices and len(grid.v_heavy_indices) > 1:
        v_stride = grid.v_heavy_indices[1] - grid.v_heavy_indices[0]
        print(f"Heavy V lines: {len(grid.v_heavy_indices)} (every {v_stride} lines)")

    # --- Stage 5: Debug image ---
    if args.debug_image:
        # Left panel: original + fragments
        left = image.copy()
        h_tuples = [(s.x1, s.y1, s.x2, s.y2) for s in geo.h_fragments]
        v_tuples = [(s.x1, s.y1, s.x2, s.y2) for s in geo.v_fragments]
        left = draw_lines(left, h_tuples, color=(0, 0, 255), thickness=2)
        left = draw_lines(left, v_tuples, color=(255, 0, 0), thickness=2)

        # Right panel: corrected + grid overlay
        right = corrected.copy()

        # Fine grid in green (thin)
        right = draw_grid(
            right, grid.h_positions, grid.v_positions,
            color=(0, 180, 0), thickness=1,
        )

        # Heavy lines in red (thick)
        heavy_h = [grid.h_positions[i] for i in grid.h_heavy_indices
                    if i < len(grid.h_positions)]
        heavy_v = [grid.v_positions[i] for i in grid.v_heavy_indices
                    if i < len(grid.v_positions)]
        if heavy_h or heavy_v:
            right = draw_grid(
                right, heavy_h, heavy_v,
                color=(0, 0, 255), thickness=2,
            )

        save_side_by_side(left, right, args.debug_image)
        print(f"Debug image saved to {args.debug_image}")


if __name__ == "__main__":
    main()
