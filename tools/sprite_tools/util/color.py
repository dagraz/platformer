"""Color conversion and background sampling utilities."""

import math

import numpy as np


def rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert RGB (0-255) to HSL. Returns (h: 0-360, s: 0-100, l: 0-100)."""
    r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
    c_max = max(r_norm, g_norm, b_norm)
    c_min = min(r_norm, g_norm, b_norm)
    delta = c_max - c_min

    # Lightness
    l = (c_max + c_min) / 2.0

    if delta == 0:
        h = 0.0
        s = 0.0
    else:
        # Saturation
        s = delta / (1.0 - abs(2.0 * l - 1.0))

        # Hue
        if c_max == r_norm:
            h = 60.0 * (((g_norm - b_norm) / delta) % 6)
        elif c_max == g_norm:
            h = 60.0 * (((b_norm - r_norm) / delta) + 2)
        else:
            h = 60.0 * (((r_norm - g_norm) / delta) + 4)

    return (h, s * 100.0, l * 100.0)


def hsl_distance(hsl1: tuple[float, float, float], hsl2: tuple[float, float, float]) -> float:
    """Perceptual distance between two HSL colors. Returns 0-100 scale.

    Weights: hue difference (circular), saturation, lightness.
    """
    h1, s1, l1 = hsl1
    h2, s2, l2 = hsl2

    # Circular hue distance (0-180)
    dh = abs(h1 - h2)
    if dh > 180:
        dh = 360 - dh
    # Normalize to 0-100
    dh_norm = dh / 1.8

    ds = abs(s1 - s2)
    dl = abs(l1 - l2)

    # Weighted Euclidean distance
    return math.sqrt(dh_norm**2 + ds**2 + dl**2)


def sample_background_color(
    image: np.ndarray, method: str = "corners"
) -> tuple[int, int, int]:
    """Sample the background color from an image (BGR format).

    Args:
        image: BGR numpy array
        method: 'corners' samples from the four corner regions

    Returns:
        (R, G, B) median background color
    """
    h, w = image.shape[:2]
    sample_size = max(10, min(h, w) // 20)

    if method == "corners":
        corners = [
            image[:sample_size, :sample_size],          # top-left
            image[:sample_size, w - sample_size:],       # top-right
            image[h - sample_size:, :sample_size],       # bottom-left
            image[h - sample_size:, w - sample_size:],   # bottom-right
        ]
        pixels = np.concatenate([c.reshape(-1, 3) for c in corners], axis=0)
    else:
        raise ValueError(f"Unknown sampling method: {method}")

    # Median color (BGR → RGB for return)
    median_bgr = np.median(pixels, axis=0).astype(int)
    return (int(median_bgr[2]), int(median_bgr[1]), int(median_bgr[0]))


def white_balance(image: np.ndarray, sample_color: tuple[int, int, int]) -> np.ndarray:
    """Shift white point so that sample_color becomes white.

    Args:
        image: BGR numpy array
        sample_color: (R, G, B) color that should map to white

    Returns:
        White-balanced BGR image
    """
    r, g, b = sample_color
    # Avoid division by zero
    scale_b = 255.0 / max(b, 1)
    scale_g = 255.0 / max(g, 1)
    scale_r = 255.0 / max(r, 1)

    result = image.astype(np.float32)
    result[:, :, 0] *= scale_b
    result[:, :, 1] *= scale_g
    result[:, :, 2] *= scale_r

    return np.clip(result, 0, 255).astype(np.uint8)
