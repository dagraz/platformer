"""sprite-clean: Remove background from extracted cell images.

Pipeline per image:
  1. (Optional) White balance
  2. Background color removal via HSL distance
  3. Small component cleanup
  4. (Optional) Alpha erosion
  5. (Optional) Alpha feathering
"""

import argparse
import os

import cv2

from sprite_tools.core.background import (
    detect_bg_color,
    erode_alpha,
    feather_alpha,
    remove_background,
    remove_small_components,
)
from sprite_tools.util.color import white_balance
from sprite_tools.util.debug import save_side_by_side
from sprite_tools.util.image_io import load_image, save_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sprite-clean",
        description="Remove background artifacts, leaving drawings on transparent background.",
    )
    parser.add_argument("--input-dir", default="cells/", help="Directory of cell PNGs to clean")
    parser.add_argument("--output-dir", default="cleaned/", help="Directory for cleaned PNGs")
    parser.add_argument("--white-balance", action="store_true", help="Apply white balance correction")
    parser.add_argument("--wb-sample", default="corners", help="White balance sample source")
    parser.add_argument("--bg-color", default="auto", help="Background color to key out (R,G,B or 'auto')")
    parser.add_argument("--bg-tolerance", type=int, default=30, help="HSL distance tolerance (0-100)")
    parser.add_argument("--min-blob-size", type=int, default=20, help="Minimum connected component size")
    parser.add_argument("--erode", type=int, default=0, help="Erosion radius for edge cleanup")
    parser.add_argument("--feather", type=int, default=0, help="Alpha feather radius")
    parser.add_argument("--files", nargs="*", help="Process only these filenames")
    parser.add_argument("--debug-image", default=None, help="Directory for before/after debug composites")
    return parser


def _parse_bg_color(s: str) -> tuple[int, int, int] | None:
    """Parse a user-supplied background color string. Returns None for 'auto'."""
    if s.lower() == "auto":
        return None
    parts = [int(x.strip()) for x in s.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Expected R,G,B — got: {s}")
    return (parts[0], parts[1], parts[2])


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Discover input files
    if not os.path.isdir(args.input_dir):
        parser.error(f"Input directory not found: {args.input_dir}")

    all_files = sorted(
        f for f in os.listdir(args.input_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    )

    if args.files:
        files = [f for f in all_files if f in args.files]
    else:
        files = all_files

    if not files:
        print("No files to process.")
        return

    os.makedirs(args.output_dir, exist_ok=True)
    if args.debug_image:
        os.makedirs(args.debug_image, exist_ok=True)

    # Parse background color
    explicit_bg = _parse_bg_color(args.bg_color)

    # Detect background color once across all cells.
    # Per-cell corner sampling fails when art extends to corners.
    if explicit_bg is not None:
        bg_rgb = explicit_bg
    else:
        import numpy as np
        all_corners = []
        for filename in files:
            img = load_image(os.path.join(args.input_dir, filename))
            h, w = img.shape[:2]
            s = max(5, min(h, w) // 10)
            for corner in [img[:s, :s], img[:s, w-s:], img[h-s:, :s], img[h-s:, w-s:]]:
                all_corners.append(corner.reshape(-1, 3))
        pixels = np.concatenate(all_corners, axis=0)
        median_bgr = np.median(pixels, axis=0).astype(int)
        bg_rgb = (int(median_bgr[2]), int(median_bgr[1]), int(median_bgr[0]))

    print(f"Processing {len(files)} files from {args.input_dir}")
    print(f"Background color: ({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]})")

    for filename in files:
        filepath = os.path.join(args.input_dir, filename)
        image = load_image(filepath)

        # Step 1: White balance
        if args.white_balance:
            from sprite_tools.util.color import sample_background_color
            sample = sample_background_color(image, args.wb_sample)
            image = white_balance(image, sample)

        # Step 3: Remove background
        bgra = remove_background(image, bg_rgb, args.bg_tolerance)

        # Step 4: Small component cleanup
        alpha = bgra[:, :, 3]
        alpha = remove_small_components(alpha, args.min_blob_size)

        # Step 5: Erosion
        if args.erode > 0:
            alpha = erode_alpha(alpha, args.erode)

        # Step 6: Feathering
        if args.feather > 0:
            alpha = feather_alpha(alpha, args.feather)

        bgra[:, :, 3] = alpha

        # Save output
        out_name = os.path.splitext(filename)[0] + ".png"
        out_path = os.path.join(args.output_dir, out_name)
        save_image(bgra, out_path)

        opaque_pct = (alpha > 0).sum() / alpha.size * 100
        print(f"  {filename}: bg=({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]})"
              f"  {opaque_pct:.0f}% opaque")

        # Debug composite
        if args.debug_image:
            # Show original on left, cleaned on checkerboard on right
            debug_path = os.path.join(args.debug_image, out_name)
            # Create checkerboard background for transparency visualization
            h, w = bgra.shape[:2]
            checker = _checkerboard(w, h, 8)
            # Composite BGRA onto checkerboard
            a = bgra[:, :, 3:4].astype(float) / 255.0
            composited = (bgra[:, :, :3].astype(float) * a +
                          checker.astype(float) * (1 - a))
            composited = composited.astype(image.dtype)
            save_side_by_side(image, composited, debug_path)

    print(f"\nCleaned {len(files)} files to {args.output_dir}")


def _checkerboard(w: int, h: int, size: int) -> "np.ndarray":
    """Generate a gray checkerboard pattern for transparency visualization."""
    import numpy as np
    rows = (np.arange(h) // size) % 2
    cols = (np.arange(w) // size) % 2
    pattern = rows[:, None] ^ cols[None, :]
    gray = np.where(pattern, 200, 240).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


if __name__ == "__main__":
    main()
