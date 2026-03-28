"""sprite-assemble: Assemble normalized frames into a sprite sheet."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-assemble",
        description="Assemble normalized frames into a sprite sheet PNG + engine manifest JSON.",
    )
    parser.add_argument("--input-dir", default="normalized/", help="Directory of normalized PNGs")
    parser.add_argument("--meta", default="cells.json", help="Path to cell metadata")
    parser.add_argument("--output", default="player.png", help="Output sprite sheet path")
    parser.add_argument("--manifest", default="player.manifest.json", help="Output manifest path")
    parser.add_argument("--fps", default="idle=4,walk=10,jump=1,fall=1,climb=6", help="FPS per state")
    parser.add_argument("--columns", default="auto", help="Column count (auto = max frame count)")
    parser.add_argument("--state-order", default="idle,walk,jump,fall,climb", help="Row ordering")
    parser.add_argument("--padding", type=int, default=0, help="Transparent padding between frames")
    parser.add_argument("--duplicate", default=None, help="Fill rules: idle=4,climb=2")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    print(f"sprite-assemble: not yet implemented (input-dir: {args.input_dir})")
    sys.exit(1)


if __name__ == "__main__":
    main()
