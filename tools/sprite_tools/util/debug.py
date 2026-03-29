"""Debug visualization helpers for overlaying detected features on images."""

from pathlib import Path

import cv2
import numpy as np


def draw_lines(
    image: np.ndarray,
    lines: list[tuple[float, float, float, float]],
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 2,
) -> np.ndarray:
    """Draw line segments on a copy of the image.

    Args:
        image: BGR image
        lines: List of (x1, y1, x2, y2) tuples
        color: BGR color
        thickness: Line thickness in pixels

    Returns:
        Copy of image with lines drawn
    """
    result = image.copy()
    for x1, y1, x2, y2 in lines:
        cv2.line(result, (int(x1), int(y1)), (int(x2), int(y2)), color, thickness)
    return result


def draw_rects(
    image: np.ndarray,
    rects: list[tuple[int, int, int, int]],
    colors: tuple[int, int, int] | list[tuple[int, int, int]] = (0, 255, 0),
    thickness: int = 2,
    labels: list[str] | None = None,
) -> np.ndarray:
    """Draw rectangles (and optional labels) on a copy of the image.

    Args:
        image: BGR image
        rects: List of (x, y, width, height) tuples
        colors: Single BGR color or list of colors per rect
        thickness: Line thickness
        labels: Optional text labels per rect

    Returns:
        Copy of image with rectangles drawn
    """
    result = image.copy()
    for i, (x, y, w, h) in enumerate(rects):
        c = colors[i] if isinstance(colors, list) else colors
        cv2.rectangle(result, (x, y), (x + w, y + h), c, thickness)
        if labels and i < len(labels):
            cv2.putText(
                result, labels[i], (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1,
            )
    return result


def draw_grid(
    image: np.ndarray,
    h_lines: list[float],
    v_lines: list[float],
    color: tuple[int, int, int] = (0, 0, 255),
    thickness: int = 1,
) -> np.ndarray:
    """Draw a grid overlay from horizontal and vertical line positions.

    Args:
        image: BGR image
        h_lines: Y-positions of horizontal lines
        v_lines: X-positions of vertical lines
        color: BGR color
        thickness: Line thickness

    Returns:
        Copy of image with grid drawn
    """
    result = image.copy()
    h, w = image.shape[:2]
    for y in h_lines:
        cv2.line(result, (0, int(y)), (w, int(y)), color, thickness)
    for x in v_lines:
        cv2.line(result, (int(x), 0), (int(x), h), color, thickness)
    return result


def draw_density_profile(
    profile: np.ndarray,
    path: str | Path,
    width: int = 800,
    height: int = 200,
    color: tuple[int, int, int] = (0, 0, 200),
    markers: list[float] | None = None,
    marker_color: tuple[int, int, int] = (0, 200, 0),
) -> None:
    """Plot a 1D density signal as an image and save it.

    Args:
        profile: 1D numpy array of values
        path: Output file path
        width: Image width in pixels
        height: Image height in pixels
        color: BGR color for the profile line
        markers: Optional x-positions to mark with vertical lines
        marker_color: BGR color for marker lines
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    n = len(profile)
    if n == 0:
        cv2.imwrite(str(path), canvas)
        return

    # Normalize profile to fit canvas height (leave 10px margin)
    p = profile.astype(np.float64)
    pmin, pmax = p.min(), p.max()
    if pmax - pmin > 0:
        p = (p - pmin) / (pmax - pmin)
    else:
        p = np.zeros_like(p)

    margin = 10
    usable = height - 2 * margin

    # Draw the profile as connected line segments
    for i in range(n - 1):
        x1 = int(i * (width - 1) / (n - 1))
        x2 = int((i + 1) * (width - 1) / (n - 1))
        y1 = height - margin - int(p[i] * usable)
        y2 = height - margin - int(p[i + 1] * usable)
        cv2.line(canvas, (x1, y1), (x2, y2), color, 1)

    # Draw markers
    if markers:
        for pos in markers:
            x = int(pos * (width - 1) / (n - 1)) if n > 1 else 0
            if 0 <= x < width:
                cv2.line(canvas, (x, 0), (x, height), marker_color, 1)

    cv2.imwrite(str(path), canvas)


def save_side_by_side(
    image_a: np.ndarray,
    image_b: np.ndarray,
    path: str | Path,
    gap: int = 10,
) -> None:
    """Save a before/after composite image.

    Resizes both images to the same height before compositing.

    Args:
        image_a: Left image (BGR)
        image_b: Right image (BGR)
        path: Output file path
        gap: Pixel gap between images
    """
    ha, wa = image_a.shape[:2]
    hb, wb = image_b.shape[:2]
    target_h = max(ha, hb)

    # Resize to match height
    if ha != target_h:
        scale = target_h / ha
        image_a = cv2.resize(image_a, (int(wa * scale), target_h))
        wa = image_a.shape[1]
    if hb != target_h:
        scale = target_h / hb
        image_b = cv2.resize(image_b, (int(wb * scale), target_h))
        wb = image_b.shape[1]

    composite = np.full((target_h, wa + gap + wb, 3), 200, dtype=np.uint8)
    composite[:, :wa] = image_a[:, :wa] if image_a.ndim == 3 else cv2.cvtColor(image_a, cv2.COLOR_GRAY2BGR)
    composite[:, wa + gap:wa + gap + wb] = image_b[:, :wb] if image_b.ndim == 3 else cv2.cvtColor(image_b, cv2.COLOR_GRAY2BGR)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), composite)
