"""sprite-pipeline: Run the full sprite extraction pipeline in one command.

Chains: grid-detect → extract → clean → normalize → assemble
        grid-detect → extract → clean → normalize → tile export (--tiles)
"""

import argparse
import json
import os
import shutil
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
        help="Output sprite sheet path, or output directory when --tiles is set",
    )
    parser.add_argument(
        "--manifest", default=None,
        help="Output manifest path (default: <output>.manifest.json)",
    )
    parser.add_argument(
        "--tiles", action="store_true",
        help="Tile mode: export individual PNGs instead of assembling a sprite sheet. "
             "-o sets the output directory.",
    )
    parser.add_argument(
        "--work-dir", default="sprite_work/",
        help="Working directory for intermediate files (default: sprite_work/)",
    )

    # Template (graph paper legacy)
    parser.add_argument(
        "--template", default=None,
        help="Path to template grid.json from blank sheet (graph paper workflow)",
    )

    # Border detection (printed template workflow)
    parser.add_argument(
        "--detect-borders", action="store_true",
        help="Use border-based detection for printed template scans",
    )
    parser.add_argument(
        "--template-meta", default=None,
        help="Path to template-meta.json (from sprite-template)",
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

    # Step 1: Grid detection
    cmd = [
        "sprite-grid-detect",
        "-i", args.input,
        "-o", grid_json,
        "--corrected-image", corrected,
        "--correct", args.correct,
    ]
    if args.detect_borders:
        cmd += ["--detect-borders"]
        if args.template_meta:
            cmd += ["--template-meta", args.template_meta]
    elif args.template:
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

    if args.tiles:
        # Tile mode: export individual PNGs named by row label and frame index
        tiles_dir = args.output
        os.makedirs(tiles_dir, exist_ok=True)

        with open(cells_json) as f:
            cells_meta = json.load(f)

        exported = []
        for cell in cells_meta["cells"]:
            src = os.path.join(normalized_dir, cell["filename"])
            if not os.path.exists(src):
                continue
            # Name: rowlabel_frameindex.png (e.g. trees_0.png, bushes_2.png)
            dst_name = f"{cell['state']}_{cell['frame']}.png"
            dst = os.path.join(tiles_dir, dst_name)
            shutil.copy2(src, dst)
            exported.append(dst_name)

        print(f"\n{'='*60}")
        print(f"  Step 5: Export tiles")
        print(f"{'='*60}")
        print(f"Exported {len(exported)} tiles to {tiles_dir}/")
        for name in exported:
            print(f"  {name}")

        print(f"\nDone! Output:")
        print(f"  Tiles directory: {tiles_dir}")
    else:
        # Sprite sheet mode: assemble into a single sheet + manifest
        manifest = args.manifest or os.path.splitext(args.output)[0] + ".manifest.json"

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
