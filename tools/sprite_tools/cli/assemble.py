"""sprite-assemble: Assemble normalized frames into a sprite sheet.

Reads cells.json metadata + normalized PNGs, composites them into a
grid sprite sheet, and generates a manifest JSON matching the engine's
SpriteManifest format.
"""

import argparse
import json
import os

import cv2
import numpy as np

from sprite_tools.util.image_io import load_image_rgba, save_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-assemble",
        description="Assemble normalized frames into a sprite sheet PNG + engine manifest JSON.",
    )
    parser.add_argument("--input-dir", default="normalized/", help="Directory of normalized PNGs")
    parser.add_argument("--meta", default="cells.json", help="Path to cell metadata")
    parser.add_argument("--output", default="player.png", help="Output sprite sheet path")
    parser.add_argument("--manifest", default="player.manifest.json", help="Output manifest path")
    parser.add_argument("--fps", default="idle=4,walk=10,jump=1,fall=1,climb=6",
                        help="FPS per state (e.g. idle=4,walk=10)")
    parser.add_argument("--columns", default="auto",
                        help="Column count (auto = max frame count across states)")
    parser.add_argument("--state-order", default=None,
                        help="Row ordering (default: from cells.json)")
    parser.add_argument("--padding", type=int, default=0,
                        help="Transparent padding between frames")
    parser.add_argument("--duplicate", default=None,
                        help="Duplicate frames to fill row: idle=4,climb=2")
    return parser


def _parse_kv(s: str) -> dict[str, int]:
    """Parse 'key=val,key=val' into a dict."""
    result = {}
    for pair in s.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = int(v.strip())
    return result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load metadata
    with open(args.meta) as f:
        meta = json.load(f)

    # Parse fps and duplicate maps
    fps_map = _parse_kv(args.fps)
    dup_map = _parse_kv(args.duplicate) if args.duplicate else {}

    # Group frames by state, preserving order from metadata
    state_order: list[str] = []
    state_frames: dict[str, list[str]] = {}

    for cell in meta["cells"]:
        state = cell["state"]
        filename = cell["filename"]
        if state not in state_frames:
            state_order.append(state)
            state_frames[state] = []
        state_frames[state].append(filename)

    # Override state order if specified
    if args.state_order:
        state_order = [s.strip() for s in args.state_order.split(",")]

    # Apply duplication
    for state in state_order:
        if state not in state_frames:
            continue
        frames = state_frames[state]
        target = dup_map.get(state, len(frames))
        if target > len(frames):
            # Cycle frames to fill
            original = list(frames)
            while len(frames) < target:
                frames.append(original[len(frames) % len(original)])

    # Determine grid dimensions
    max_frames = max(len(state_frames.get(s, [])) for s in state_order)
    if args.columns != "auto":
        n_cols = int(args.columns)
    else:
        n_cols = max_frames
    n_rows = len(state_order)

    # Load first frame to get dimensions
    first_file = state_frames[state_order[0]][0]
    first_frame = load_image_rgba(os.path.join(args.input_dir, first_file))
    frame_h, frame_w = first_frame.shape[:2]

    pad = args.padding
    sheet_w = n_cols * frame_w + (n_cols - 1) * pad
    sheet_h = n_rows * frame_h + (n_rows - 1) * pad

    print(f"Sheet: {n_cols} cols x {n_rows} rows"
          f" = {sheet_w}x{sheet_h}px"
          f" (frames {frame_w}x{frame_h})")

    # Composite
    sheet = np.zeros((sheet_h, sheet_w, 4), dtype=np.uint8)

    for row_idx, state in enumerate(state_order):
        frames = state_frames.get(state, [])
        y = row_idx * (frame_h + pad)

        for col_idx, filename in enumerate(frames):
            if col_idx >= n_cols:
                break
            x = col_idx * (frame_w + pad)
            filepath = os.path.join(args.input_dir, filename)
            frame = load_image_rgba(filepath)

            # Handle size mismatch gracefully
            fh, fw = frame.shape[:2]
            copy_h = min(fh, frame_h, sheet_h - y)
            copy_w = min(fw, frame_w, sheet_w - x)
            if copy_h > 0 and copy_w > 0:
                sheet[y:y + copy_h, x:x + copy_w] = frame[:copy_h, :copy_w]

        n_frames = min(len(frames), n_cols)
        fps = fps_map.get(state, 8)
        print(f"  Row {row_idx}: {state} — {n_frames} frames @ {fps} fps")

    save_image(sheet, args.output)
    print(f"Sprite sheet saved to {args.output}")

    # Generate manifest matching engine SpriteManifest format
    manifest = {
        "frameWidth": frame_w,
        "frameHeight": frame_h,
        "states": {},
    }
    for row_idx, state in enumerate(state_order):
        frames = state_frames.get(state, [])
        manifest["states"][state] = {
            "row": row_idx,
            "frames": min(len(frames), n_cols),
            "fps": fps_map.get(state, 8),
        }

    with open(args.manifest, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest saved to {args.manifest}")


if __name__ == "__main__":
    main()
