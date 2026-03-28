"""sprite-extract: Extract individual cell images from a corrected scan."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-extract",
        description="Extract individual cell images using a grid definition.",
    )
    parser.add_argument("-i", "--input", default="corrected.png", help="Path to corrected image")
    parser.add_argument("-g", "--grid", default="grid.json", help="Path to grid definition")
    parser.add_argument("--output-dir", default="cells/", help="Directory for extracted cell PNGs")
    parser.add_argument("--output-meta", default="cells.json", help="Path for metadata JSON")
    parser.add_argument("--rows", required=True, help="Comma-separated row-to-state mapping")
    parser.add_argument("--skip-empty", default=True, type=bool, help="Skip unoccupied cells")
    parser.add_argument("--padding", type=int, default=0, help="Pixels to inset from cell boundary")
    parser.add_argument("--bleed", type=int, default=0, help="Pixels to expand crop beyond cell boundary")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(f"sprite-extract: not yet implemented (input: {args.input})")
    sys.exit(1)


if __name__ == "__main__":
    main()
