"""Helpers for image files used when uploading to Feishu."""
from __future__ import annotations

import os
import tempfile
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


def feishu_upload_path(file_path: str) -> tuple[str, Optional[str]]:
    """
    Return (path_to_read_for_upload, temp_path_to_delete_or_None).

    Feishu often renders WebP blocks incorrectly (tiny frame). Re-encode WebP as
    JPEG before upload; JPEG from the same pipeline displays at correct size.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return file_path, None

    try:
        with Image.open(file_path) as im:
            fmt = (im.format or "").upper()
            if fmt != "WEBP":
                return file_path, None
            im = ImageOps.exif_transpose(im)
            im.load()

            if im.mode in ("RGBA", "LA"):
                base = Image.new("RGB", im.size, (255, 255, 255))
                base.paste(im, mask=im.split()[-1])
                im = base
            elif im.mode == "P":
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")

            fd, tmp_path = tempfile.mkstemp(prefix="feishu_img_", suffix=".jpg")
            os.close(fd)
            im.save(tmp_path, format="JPEG", quality=92, optimize=True)
            return tmp_path, tmp_path
    except Exception:
        return file_path, None
