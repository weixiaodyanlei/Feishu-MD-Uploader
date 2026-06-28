from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.pdf.models import ElementKind, ExtractedImage, MdElement

logger = logging.getLogger(__name__)


def render_markdown(elements: list[MdElement], assets_dir_name: str) -> str:
    parts: list[str] = []
    for element in elements:
        if element.kind == ElementKind.HEADING:
            level = max(1, min(element.level, 3))
            parts.append(f"{'#' * level} {element.content}")
        elif element.kind == ElementKind.CODE:
            parts.append(f"```\n{element.content}\n```")
        elif element.kind == ElementKind.PARAGRAPH:
            parts.append(element.content)
        elif element.kind == ElementKind.IMAGE:
            filename = element.content
            ref = element.image_ref or f"{assets_dir_name}/{filename}"
            alt = Path(filename).stem
            parts.append(f"![{alt}]({ref})")
    return "\n\n".join(parts).strip() + "\n"


def save_images(images: list[ExtractedImage], assets_dir: Path, *, clean: bool = False) -> None:
    if clean and assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    for image in images:
        filename = f"image_{image.image_index:03d}.{image.ext}"
        target = assets_dir / filename
        try:
            target.write_bytes(image.data)
        except OSError as exc:
            logger.warning("Failed to save image %s: %s", filename, exc)
