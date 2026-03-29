"""Background removal for extracted cell images.

Pipeline: detect background color → build alpha mask via HSL distance →
remove small components → optional erosion → optional feathering.
"""

from __future__ import annotations

import cv2
import numpy as np

from sprite_tools.util.color import rgb_to_hsl, hsl_distance


def detect_bg_color(
    image_bgr: np.ndarray,
    method: str = "corners",
) -> tuple[int, int, int]:
    """Detect the background color from an image.

    Args:
        image_bgr: BGR image.
        method: 'corners' samples from the four corner regions.

    Returns:
        (R, G, B) background color.
    """
    h, w = image_bgr.shape[:2]
    sample_size = max(5, min(h, w) // 10)

    if method == "corners":
        corners = [
            image_bgr[:sample_size, :sample_size],
            image_bgr[:sample_size, w - sample_size:],
            image_bgr[h - sample_size:, :sample_size],
            image_bgr[h - sample_size:, w - sample_size:],
        ]
        pixels = np.concatenate([c.reshape(-1, 3) for c in corners], axis=0)
    else:
        raise ValueError(f"Unknown method: {method}")

    median_bgr = np.median(pixels, axis=0).astype(int)
    return (int(median_bgr[2]), int(median_bgr[1]), int(median_bgr[0]))


def remove_background(
    image_bgr: np.ndarray,
    bg_color_rgb: tuple[int, int, int],
    tolerance: float,
) -> np.ndarray:
    """Remove background by setting matching pixels to transparent.

    Computes per-pixel HSL distance from the background color. Pixels
    within tolerance become fully transparent; pixels beyond tolerance
    remain fully opaque.

    Args:
        image_bgr: BGR input image.
        bg_color_rgb: (R, G, B) background color to remove.
        tolerance: HSL distance threshold (0-100).

    Returns:
        BGRA image with alpha channel.
    """
    h, w = image_bgr.shape[:2]
    bg_hsl = rgb_to_hsl(*bg_color_rgb)

    # Convert BGR to RGB for per-pixel HSL conversion
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # Vectorized HSL distance computation
    # Convert to float for computation
    r = rgb[:, :, 0].astype(np.float64) / 255.0
    g = rgb[:, :, 1].astype(np.float64) / 255.0
    b = rgb[:, :, 2].astype(np.float64) / 255.0

    c_max = np.maximum(np.maximum(r, g), b)
    c_min = np.minimum(np.minimum(r, g), b)
    delta = c_max - c_min

    # Lightness
    l = (c_max + c_min) / 2.0

    # Saturation
    s = np.where(
        delta == 0,
        0.0,
        delta / (1.0 - np.abs(2.0 * l - 1.0) + 1e-10),
    )

    # Hue
    hue = np.zeros_like(l)
    mask_r = (c_max == r) & (delta > 0)
    mask_g = (c_max == g) & (delta > 0) & ~mask_r
    mask_b = (delta > 0) & ~mask_r & ~mask_g

    hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6)
    hue[mask_g] = 60.0 * (((b[mask_g] - r[mask_g]) / delta[mask_g]) + 2)
    hue[mask_b] = 60.0 * (((r[mask_b] - g[mask_b]) / delta[mask_b]) + 4)

    s *= 100.0
    l *= 100.0

    # HSL distance from background
    bg_h, bg_s, bg_l = bg_hsl

    dh = np.abs(hue - bg_h)
    dh = np.where(dh > 180, 360 - dh, dh)
    dh_norm = dh / 1.8

    ds = np.abs(s - bg_s)
    dl = np.abs(l - bg_l)

    dist = np.sqrt(dh_norm**2 + ds**2 + dl**2)

    # Build alpha: 0 where close to background, 255 where far
    alpha = np.where(dist <= tolerance, 0, 255).astype(np.uint8)

    # Combine into BGRA
    bgra = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha

    return bgra


def remove_small_components(
    alpha: np.ndarray,
    min_size: int,
) -> np.ndarray:
    """Remove small connected components from the alpha channel.

    Removes both small opaque blobs (noise) and small transparent holes
    (gaps in the drawing).

    Args:
        alpha: Single-channel alpha (0 or 255).
        min_size: Minimum pixel count to keep.

    Returns:
        Cleaned alpha channel.
    """
    result = alpha.copy()

    # Remove small opaque blobs
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(alpha)
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < min_size:
            result[labels == i] = 0

    # Remove small transparent holes (invert, find small components, fill)
    inv = 255 - result
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inv)
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < min_size:
            result[labels == i] = 255

    return result


def erode_alpha(alpha: np.ndarray, radius: int) -> np.ndarray:
    """Erode the alpha mask to remove fringe pixels."""
    if radius <= 0:
        return alpha
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1)
    )
    return cv2.erode(alpha, kernel)


def feather_alpha(alpha: np.ndarray, radius: int) -> np.ndarray:
    """Feather (blur) the alpha edges for smoother transparency."""
    if radius <= 0:
        return alpha
    ksize = 2 * radius + 1
    return cv2.GaussianBlur(alpha, (ksize, ksize), radius / 2)
