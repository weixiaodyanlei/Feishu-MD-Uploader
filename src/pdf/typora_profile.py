from __future__ import annotations

from collections import Counter

from src.pdf.models import TextBlock

_MONOSPACE_KEYWORDS = (
    "consolas",
    "courier new",
    "courier",
    "menlo",
    "monaco",
    "source code pro",
    "monospace",
)


def is_monospace_font(font_name: str) -> bool:
    normalized = (font_name or "").lower()
    return any(keyword in normalized for keyword in _MONOSPACE_KEYWORDS)
