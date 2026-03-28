"""sprite-normalize: Scale, align, and anchor cleaned cell images."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-normalize",
        description="Scale, align, and anchor cleaned cell images to consistent target size.",
    )
    parser.add_argument("--input-dir", default="cleaned/", help="Directory of cleaned PNGs")
    parser.add_argument("--output-dir", default="normalized/", help="Directory for normalized PNGs")
    parser.add_argument("--width", type=int, default=64, help="Target frame width")
    parser.add_argument("--height", type=int, default=128, help="Target frame height")
    parser.add_argument("--fit", default="contain", choices=["contain", "cover", "stretch", "none"], help="Fit mode")
    parser.add_argument("--anchor", default="bottom", choices=["bottom", "center", "top"], help="Vertical anchor")
    parser.add_argument("--margin", type=int, default=2, help="Pixels of margin within the frame")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(f"sprite-normalize: not yet implemented (input-dir: {args.input_dir})")
    sys.exit(1)


if __name__ == "__main__":
    main()
