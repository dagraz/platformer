"""sprite-grid-detect: Detect graph paper grid structure from a scan or photo."""

import argparse
import sys

from sprite_tools.core.grid import analyze_grid_geometry
from sprite_tools.util.debug import draw_lines
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
        help="Path to write annotated debug image",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    image = load_image(args.input)
    h, w = image.shape[:2]
    print(f"Loaded image: {w}x{h}")

    geo = analyze_grid_geometry(image)

    print(f"Fragments: {len(geo.h_fragments)} horizontal, {len(geo.v_fragments)} vertical")
    print(f"Dominant angles: H={geo.h_angle:.2f}° V={geo.v_angle:.2f}°")
    print(f"Grid period: H={geo.h_period:.1f}px V={geo.v_period:.1f}px")

    # Rotation estimate (deviation from axis-aligned)
    h_rotation = geo.h_angle if geo.h_angle < 90 else geo.h_angle - 180
    print(f"Rotation estimate: {h_rotation:.2f}°")

    # Spatial angle variation (perspective indicator)
    for direction in ["horizontal", "vertical"]:
        spatial = geo.spatial_angles[direction]
        zone_str = ", ".join(
            f"{a:.2f}°" if a == a else "n/a"  # nan check
            for a in spatial["zone_angles"]
        )
        print(f"  {direction.capitalize()} angle by zone: [{zone_str}]"
              f"  range={spatial['angle_range']:.2f}° std={spatial['angle_std']:.2f}°")

    if geo.spatial_angles["horizontal"]["angle_range"] > 2.0 or \
       geo.spatial_angles["vertical"]["angle_range"] > 2.0:
        print("  → Significant spatial variation: perspective correction likely needed")
    elif abs(h_rotation) > 0.5:
        print(f"  → Rotation correction needed: {h_rotation:.2f}°")
    else:
        print("  → Image is well-aligned (minimal correction needed)")

    # Debug image
    if args.debug_image:
        debug = image.copy()

        # Draw H fragments in red, V fragments in blue
        h_tuples = [(s.x1, s.y1, s.x2, s.y2) for s in geo.h_fragments]
        v_tuples = [(s.x1, s.y1, s.x2, s.y2) for s in geo.v_fragments]
        debug = draw_lines(debug, h_tuples, color=(0, 0, 255), thickness=2)
        debug = draw_lines(debug, v_tuples, color=(255, 0, 0), thickness=2)

        save_image(debug, args.debug_image)
        print(f"Debug image saved to {args.debug_image}")


if __name__ == "__main__":
    main()
