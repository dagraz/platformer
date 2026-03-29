"""Image loading and saving utilities."""

from pathlib import Path

import cv2
import numpy as np


def load_image(path: str | Path) -> np.ndarray:
    """Load an image as BGR numpy array via OpenCV.

    Handles JPEG and PNG. Raises FileNotFoundError if path doesn't exist,
    ValueError if the file can't be decoded as an image.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return image


def load_image_rgba(path: str | Path) -> np.ndarray:
    """Load an image as BGRA numpy array. Creates alpha channel if absent."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    if image.ndim == 2:
        # Grayscale → BGRA
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        # BGR → BGRA (fully opaque alpha)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    return image


def save_image(image: np.ndarray, path: str | Path) -> None:
    """Save an image to disk. PNG for BGRA, JPEG for BGR."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        # Strip alpha for JPEG
        if image.ndim == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    else:
        cv2.imwrite(str(path), image)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR or BGRA image to single-channel grayscale."""
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def image_dimensions(path: str | Path) -> tuple[int, int]:
    """Return (width, height) of an image without fully loading it."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    h, w = image.shape[:2]
    return (w, h)
