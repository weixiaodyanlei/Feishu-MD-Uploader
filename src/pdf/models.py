from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ElementKind(str, Enum):
    HEADING = "heading"
    CODE = "code"
    PARAGRAPH = "paragraph"
    IMAGE = "image"
    TABLE = "table"


@dataclass(frozen=True)
class TextBlock:
    text: str
    font: str
    size: float
    flags: int
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class LinkAnnotation:
    uri: str
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class ExtractedImage:
    page_index: int
    x0: float
    y0: float
    xref: int
    ext: str
    data: bytes
    image_index: int = 0  # assigned after sort: 1, 2, 3...


@dataclass
class MdElement:
    kind: ElementKind
    content: str
    level: int = 0  # heading level 1-3 only
    image_ref: Optional[str] = None  # relative path for IMAGE kind


@dataclass
class ExtractedTable:
    page_index: int
    x0: float
    y0: float
    x1: float
    y1: float
    markdown: str


@dataclass
class ExtractedDocument:
    blocks: list[TextBlock] = field(default_factory=list)
    links: list[LinkAnnotation] = field(default_factory=list)
    images: list[ExtractedImage] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
