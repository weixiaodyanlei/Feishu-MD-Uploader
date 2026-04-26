"""Helpers for image files used when uploading to Feishu."""
from __future__ import annotations

from typing import Optional, Tuple


def read_image_pixel_size(file_path: str) -> Optional[Tuple[int, int]]:
    """
    Return (width, height) in pixels for display, or None if unknown.

    Applies EXIF orientation so size matches visible pixels.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    try:
        with Image.open(file_path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            if w > 0 and h > 0:
                return (int(w), int(h))
    except Exception:
        return None
    return None
