from __future__ import annotations

from collections import Counter

from src.pdf.models import LinkAnnotation, TextBlock

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


def detect_body_size(blocks: list[TextBlock]) -> float:
    sizes = [b.size for b in blocks if b.text.strip() and not is_monospace_font(b.font)]
    if not sizes:
        sizes = [b.size for b in blocks if b.text.strip()]
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]


def build_heading_size_map(blocks: list[TextBlock], body_size: float) -> list[float]:
    sizes = {
        b.size
        for b in blocks
        if b.text.strip() and b.size > body_size and not is_monospace_font(b.font)
    }
    return sorted(sizes, reverse=True)


def map_heading_level(
    size: float,
    font: str,
    body_size: float,
    heading_sizes: list[float],
) -> int | None:
    if is_monospace_font(font) or size <= body_size:
        return None
    if not heading_sizes:
        return None
    top_three = heading_sizes[:3]
    if size in top_three:
        return top_three.index(size) + 1
    return 3


def merge_code_blocks(blocks: list[TextBlock]) -> list[list[TextBlock]]:
    groups: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    blank_gap = 0

    for block in blocks:
        if is_monospace_font(block.font):
            if current and blank_gap > 1:
                groups.append(current)
                current = []
            current.append(block)
            blank_gap = 0
            continue

        if current and not block.text.strip():
            blank_gap += 1
            current.append(block)
            continue

        if current:
            groups.append(current)
            current = []
            blank_gap = 0

    if current:
        groups.append(current)

    return groups
