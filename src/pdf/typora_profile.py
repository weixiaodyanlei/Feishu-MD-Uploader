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


def rects_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and ax1 > bx0 and ay0 < by1 and ay1 > by0


def _block_rect(block: TextBlock) -> tuple[float, float, float, float]:
    return (block.x0, block.y0, block.x1, block.y1)


def match_link_to_text(link: LinkAnnotation, blocks: list[TextBlock]) -> str | None:
    candidates: list[tuple[float, TextBlock]] = []
    link_rect = (link.x0, link.y0, link.x1, link.y1)
    for block in blocks:
        if block.page_index != link.page_index or not block.text.strip():
            continue
        block_rect = _block_rect(block)
        if rects_overlap(link_rect, block_rect):
            overlap_x = min(link.x1, block.x1) - max(link.x0, block.x0)
            overlap_y = min(link.y1, block.y1) - max(link.y0, block.y0)
            score = overlap_x * overlap_y
            candidates.append((score, block))
    if not candidates:
        return None
    best = max(candidates, key=lambda item: item[0])[1]
    return best.text.strip()


def apply_links_to_blocks(
    blocks: list[TextBlock],
    links: list[LinkAnnotation],
) -> list[TextBlock]:
    if not links:
        return blocks

    linked_text_by_id: dict[int, str] = {}
    for link in links:
        matched = match_link_to_text(link, blocks)
        if matched is None:
            continue
        for idx, block in enumerate(blocks):
            if block.page_index == link.page_index and block.text.strip() == matched:
                if idx not in linked_text_by_id:
                    linked_text_by_id[idx] = f"[{matched}]({link.uri})"
                break

    result: list[TextBlock] = []
    for idx, block in enumerate(blocks):
        if idx in linked_text_by_id:
            block = TextBlock(
                text=linked_text_by_id[idx],
                font=block.font,
                size=block.size,
                flags=block.flags,
                page_index=block.page_index,
                x0=block.x0,
                y0=block.y0,
                x1=block.x1,
                y1=block.y1,
            )
        result.append(block)
    return result
