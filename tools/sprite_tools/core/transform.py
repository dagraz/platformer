"""Image transformation utilities for sprite normalization.

Finds art bounds within transparent images, computes scale factors,
and fits art into target frames with anchoring.
"""

from __future__ import annotations

import cv2
import numpy as np


def find_art_bounds(image_rgba: np.ndarray) -> tuple[int, int, int, int]:
    """Find the bounding box of non-transparent pixels.

    Args:
        image_rgba: BGRA image with alpha channel.

    Returns:
        (x, y, width, height) of the tight bounding box around opaque content.
        Returns (0, 0, 0, 0) if the image is fully transparent.
    """
    alpha = image_rgba[:, :, 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)

    if not rows.any():
        return (0, 0, 0, 0)

    y0 = int(np.argmax(rows))
    y1 = int(len(rows) - np.argmax(rows[::-1]))
    x0 = int(np.argmax(cols))
    x1 = int(len(cols) - np.argmax(cols[::-1]))

    return (x0, y0, x1 - x0, y1 - y0)


def compute_scale_factor(
    art_w: int,
    art_h: int,
    target_w: int,
    target_h: int,
    fit: str,
    margin: int,
) -> float:
    """Compute the scale factor to fit art into the target frame.

    Args:
        art_w, art_h: Size of the art bounding box.
        target_w, target_h: Target frame size.
        fit: 'contain' (fit inside), 'cover' (fill frame), 'none' (1:1).
        margin: Pixels of margin within the frame on each side.

    Returns:
        Scale factor to apply to the art.
    """
    if art_w <= 0 or art_h <= 0:
        return 1.0

    usable_w = max(1, target_w - 2 * margin)
    usable_h = max(1, target_h - 2 * margin)

    if fit == "contain":
        return min(usable_w / art_w, usable_h / art_h)
    elif fit == "cover":
        return max(usable_w / art_w, usable_h / art_h)
    elif fit == "none":
        return 1.0
    else:
        raise ValueError(f"Unknown fit mode: {fit}")


def fit_to_frame(
    image_rgba: np.ndarray,
    target_w: int,
    target_h: int,
    fit: str = "contain",
    anchor: str = "bottom",
    margin: int = 0,
) -> np.ndarray:
    """Scale and place art within a target-sized transparent frame.

    Crops to art bounds, scales according to fit mode, then places
    within a target_w × target_h frame at the specified anchor position.

    Args:
        image_rgba: BGRA image with alpha channel.
        target_w, target_h: Output frame size.
        fit: 'contain', 'cover', or 'none'.
        anchor: 'bottom', 'center', or 'top' — vertical placement.
        margin: Pixels of margin on each side.

    Returns:
        BGRA image of exactly target_w × target_h.
    """
    x, y, art_w, art_h = find_art_bounds(image_rgba)

    # Create empty output frame
    frame = np.zeros((target_h, target_w, 4), dtype=np.uint8)

    if art_w <= 0 or art_h <= 0:
        return frame

    # Crop to art bounds
    art = image_rgba[y:y + art_h, x:x + art_w]

    # Scale
    scale = compute_scale_factor(art_w, art_h, target_w, target_h, fit, margin)
    scaled_w = max(1, int(round(art_w * scale)))
    scaled_h = max(1, int(round(art_h * scale)))
    scaled = cv2.resize(art, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

    # Horizontal: center
    paste_x = (target_w - scaled_w) // 2

    # Vertical: anchor
    if anchor == "bottom":
        paste_y = target_h - margin - scaled_h
    elif anchor == "top":
        paste_y = margin
    elif anchor == "center":
        paste_y = (target_h - scaled_h) // 2
    else:
        raise ValueError(f"Unknown anchor: {anchor}")

    # Clamp paste region to frame bounds
    src_x0 = max(0, -paste_x)
    src_y0 = max(0, -paste_y)
    dst_x0 = max(0, paste_x)
    dst_y0 = max(0, paste_y)
    copy_w = min(scaled_w - src_x0, target_w - dst_x0)
    copy_h = min(scaled_h - src_y0, target_h - dst_y0)

    if copy_w > 0 and copy_h > 0:
        frame[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = \
            scaled[src_y0:src_y0 + copy_h, src_x0:src_x0 + copy_w]

    return frame
