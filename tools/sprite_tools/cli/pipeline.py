"""sprite-pipeline: Run the full sprite extraction pipeline in one command.

Chains: grid-detect → extract → clean → normalize → assemble
"""

import argparse
import os
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-pipeline",
        description="Run the full sprite extraction pipeline from scan to sprite sheet.",
    )

    # Required
    parser.add_argument(
        "-i", "--input", required=True,
        help="Path to the scanned sprite sheet image",
    )
    parser.add_argument(
        "--rows", required=True,
        help="Comma-separated state names for each row (e.g. idle,walk,jump,fall,climb)",
    )

    # Output
    parser.add_argument(
        "-o", "--output", default="player.png",
        help="Output sprite sheet path (default: player.png)",
    )
    parser.add_argument(
        "--manifest", default=None,
        help="Output manifest path (default: <output>.manifest.json)",
    )
    parser.add_argument(
        "--work-dir", default="sprite_work/",
        help="Working directory for intermediate files (default: sprite_work/)",
    )

    # Template
    parser.add_argument(
        "--template", default=None,
        help="Path to template grid.json from blank sheet (recommended)",
    )

    # Grid detection
    parser.add_argument(
        "--correct", default="auto",
        choices=["auto", "rotation", "perspective", "none"],
        help="Geometric correction mode (default: auto)",
    )

    # Extraction
    parser.add_argument(
        "--padding", type=int, default=2,
        help="Pixels to inset from cell boundary (default: 2)",
    )

    # Cleaning
    parser.add_argument(
        "--bg-tolerance", type=int, default=30,
        help="Background removal HSL distance tolerance (default: 30)",
    )
    parser.add_argument(
        "--erode", type=int, default=0,
        help="Alpha erosion radius (default: 0)",
    )

    # Normalize
    parser.add_argument(
        "--width", type=int, default=64,
        help="Target frame width (default: 64)",
    )
    parser.add_argument(
        "--height", type=int, default=128,
        help="Target frame height (default: 128)",
    )
    parser.add_argument(
        "--anchor", default="bottom",
        choices=["bottom", "center", "top"],
        help="Vertical anchor (default: bottom)",
    )
    parser.add_argument(
        "--margin", type=int, default=2,
        help="Frame margin in pixels (default: 2)",
    )

    # Assemble
    parser.add_argument(
        "--fps", default="idle=4,walk=10,jump=1,fall=1,climb=6",
        help="FPS per state",
    )
    parser.add_argument(
        "--duplicate", default=None,
        help="Duplicate frames to fill rows (e.g. idle=4,climb=2)",
    )

    # Debug
    parser.add_argument(
        "--debug", action="store_true",
        help="Save debug images at each stage",
    )

    return parser


def _run(cmd: list[str], label: str) -> None:
    """Run a subprocess, printing the command and forwarding output."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  $ {' '.join(cmd)}")
    print(f"{'='*60}", flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: {label} failed (exit code {result.returncode})")
        sys.exit(result.returncode)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    work = args.work_dir
    os.makedirs(work, exist_ok=True)

    grid_json = os.path.join(work, "grid.json")
    corrected = os.path.join(work, "corrected.png")
    cells_dir = os.path.join(work, "cells")
    cells_json = os.path.join(work, "cells.json")
    cleaned_dir = os.path.join(work, "cleaned")
    normalized_dir = os.path.join(work, "normalized")
    manifest = args.manifest or os.path.splitext(args.output)[0] + ".manifest.json"

    # Step 1: Grid detection
    cmd = [
        "sprite-grid-detect",
        "-i", args.input,
        "-o", grid_json,
        "--corrected-image", corrected,
        "--correct", args.correct,
    ]
    if args.template:
        cmd += ["--template", args.template]
    if args.debug:
        cmd += ["--debug-image", os.path.join(work, "debug_grid.png")]
    _run(cmd, "Step 1: Grid detection")

    # Step 2: Extract cells
    cmd = [
        "sprite-extract",
        "-i", corrected,
        "-g", grid_json,
        "--rows", args.rows,
        "--padding", str(args.padding),
        "--output-dir", cells_dir,
        "--output-meta", cells_json,
    ]
    _run(cmd, "Step 2: Extract cells")

    # Step 3: Clean backgrounds
    cmd = [
        "sprite-clean",
        "--input-dir", cells_dir,
        "--output-dir", cleaned_dir,
        "--bg-tolerance", str(args.bg_tolerance),
    ]
    if args.erode > 0:
        cmd += ["--erode", str(args.erode)]
    if args.debug:
        cmd += ["--debug-image", os.path.join(work, "debug_clean")]
    _run(cmd, "Step 3: Clean backgrounds")

    # Step 4: Normalize
    cmd = [
        "sprite-normalize",
        "--input-dir", cleaned_dir,
        "--output-dir", normalized_dir,
        "--width", str(args.width),
        "--height", str(args.height),
        "--anchor", args.anchor,
        "--margin", str(args.margin),
    ]
    _run(cmd, "Step 4: Normalize")

    # Step 5: Assemble
    cmd = [
        "sprite-assemble",
        "--input-dir", normalized_dir,
        "--meta", cells_json,
        "--output", args.output,
        "--manifest", manifest,
        "--fps", args.fps,
    ]
    if args.duplicate:
        cmd += ["--duplicate", args.duplicate]
    _run(cmd, "Step 5: Assemble sprite sheet")

    print(f"\nDone! Output:")
    print(f"  Sprite sheet: {args.output}")
    print(f"  Manifest:     {manifest}")


if __name__ == "__main__":
    main()
