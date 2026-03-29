"""sprite-normalize: Scale, align, and anchor cleaned cell images.

Reads cleaned PNGs (transparent backgrounds), finds the art bounding box,
scales to fit the target frame, and anchors (bottom/center/top).
"""

import argparse
import os

from sprite_tools.core.transform import find_art_bounds, fit_to_frame
from sprite_tools.util.image_io import load_image_rgba, save_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-normalize",
        description="Scale, align, and anchor cleaned cell images to consistent target size.",
    )
    parser.add_argument("--input-dir", default="cleaned/", help="Directory of cleaned PNGs")
    parser.add_argument("--output-dir", default="normalized/", help="Directory for normalized PNGs")
    parser.add_argument("--width", type=int, default=64, help="Target frame width")
    parser.add_argument("--height", type=int, default=128, help="Target frame height")
    parser.add_argument("--fit", default="contain", choices=["contain", "cover", "stretch", "none"],
                        help="Fit mode (default: contain)")
    parser.add_argument("--anchor", default="bottom", choices=["bottom", "center", "top"],
                        help="Vertical anchor (default: bottom)")
    parser.add_argument("--margin", type=int, default=2, help="Pixels of margin within the frame")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory not found: {args.input_dir}")

    files = sorted(
        f for f in os.listdir(args.input_dir)
        if f.lower().endswith(".png")
    )

    if not files:
        print("No files to process.")
        return

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Normalizing {len(files)} files to {args.width}x{args.height}"
          f" (fit={args.fit}, anchor={args.anchor}, margin={args.margin})")

    for filename in files:
        filepath = os.path.join(args.input_dir, filename)
        image = load_image_rgba(filepath)

        x, y, art_w, art_h = find_art_bounds(image)

        frame = fit_to_frame(
            image,
            target_w=args.width,
            target_h=args.height,
            fit=args.fit,
            anchor=args.anchor,
            margin=args.margin,
        )

        out_path = os.path.join(args.output_dir, filename)
        save_image(frame, out_path)

        if art_w > 0 and art_h > 0:
            from sprite_tools.core.transform import compute_scale_factor
            scale = compute_scale_factor(
                art_w, art_h, args.width, args.height, args.fit, args.margin,
            )
            print(f"  {filename}: art={art_w}x{art_h}  scale={scale:.3f}")
        else:
            print(f"  {filename}: (empty)")

    print(f"\nNormalized {len(files)} files to {args.output_dir}")


if __name__ == "__main__":
    main()
