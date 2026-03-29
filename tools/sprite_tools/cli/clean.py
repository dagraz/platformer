"""sprite-clean: Remove background artifacts from extracted cell images."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-clean",
        description="Remove background artifacts, leaving drawings on transparent background.",
    )
    parser.add_argument("--input-dir", default="cells/", help="Directory of cell PNGs to clean")
    parser.add_argument("--output-dir", default="cleaned/", help="Directory for cleaned PNGs")
    parser.add_argument("--white-balance", action="store_true", help="Apply white balance correction")
    parser.add_argument("--wb-sample", default="corners", help="White balance sample source")
    parser.add_argument("--bg-color", default="auto", help="Background color to key out (hex)")
    parser.add_argument("--bg-tolerance", type=int, default=30, help="HSL distance tolerance (0-100)")
    parser.add_argument("--min-blob-size", type=int, default=20, help="Minimum connected component size")
    parser.add_argument("--erode", type=int, default=0, help="Erosion radius for edge cleanup")
    parser.add_argument("--feather", type=int, default=0, help="Alpha feather radius")
    parser.add_argument("--files", nargs="*", help="Process only these filenames")
    parser.add_argument("--debug-image", default=None, help="Write before/after debug composites")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(f"sprite-clean: not yet implemented (input-dir: {args.input_dir})")
    sys.exit(1)


if __name__ == "__main__":
    main()
