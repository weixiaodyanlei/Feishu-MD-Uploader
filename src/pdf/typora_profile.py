from __future__ import annotations

import logging
import re
from collections import Counter

from src.pdf.models import ElementKind, ExtractedDocument, LinkAnnotation, MdElement, TextBlock
from src.pdf.table_utils import filter_blocks_outside_tables

logger = logging.getLogger(__name__)

_LIST_UNORDERED = re.compile(r"^[-*+•]\s")
_LIST_ORDERED = re.compile(r"^\d+\.\s")

_MONOSPACE_KEYWORDS = (
    "consolas",
    "courier new",
    "courier",
    "menlo",
    "monaco",
    "source code pro",
    "monospace",
    "lucida",
    "lucidaconsole",
    "dejavu",
    "liberation mono",
    "jetbrains",
    "fira code",
    "sf mono",
    "inconsolata",
)


def is_monospace_font(font_name: str) -> bool:
    normalized = (font_name or "").lower()
    return any(keyword in normalized for keyword in _MONOSPACE_KEYWORDS)


def is_code_font(font_name: str) -> bool:
    """Detect PDF code fonts (Typora often uses Lucida Console on Windows)."""
    return is_monospace_font(font_name)


def _is_line_number_gutter(block: TextBlock) -> bool:
    """Strip PDF/Typora line-number gutter cells (e.g. '1', '2' at far left)."""
    text = block.text.strip()
    if not text.isdigit() or len(text) > 3:
        return False
    return block.x0 < 100


def _code_text_from_group(group: list[TextBlock]) -> str:
    lines = [b.text for b in group if b.text.strip() and not _is_line_number_gutter(b)]
    return "\n".join(lines).strip("\n")


def detect_body_size(blocks: list[TextBlock]) -> float:
    sizes = [b.size for b in blocks if b.text.strip() and not is_code_font(b.font)]
    if not sizes:
        sizes = [b.size for b in blocks if b.text.strip()]
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]


def build_heading_size_map(blocks: list[TextBlock], body_size: float) -> list[float]:
    sizes = {
        b.size
        for b in blocks
        if b.text.strip() and b.size > body_size and not is_code_font(b.font)
    }
    return sorted(sizes, reverse=True)


def map_heading_level(
    size: float,
    font: str,
    body_size: float,
    heading_sizes: list[float],
) -> int | None:
    if is_code_font(font) or size <= body_size:
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
        if is_code_font(block.font):
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
    unmatched_links: list[LinkAnnotation] = []
    for link in links:
        matched = match_link_to_text(link, blocks)
        if matched is None:
            unmatched_links.append(link)
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

    for link in unmatched_links:
        result.append(
            TextBlock(
                text=link.uri,
                font="",
                size=0.0,
                flags=0,
                page_index=link.page_index,
                x0=link.x0,
                y0=link.y0,
                x1=link.x1,
                y1=link.y1,
            )
        )
    result.sort(key=lambda b: (b.page_index, b.y0, b.x0))
    return result


def _sort_key_page_y_x(page_index: int, y0: float, x0: float) -> tuple[int, float, float]:
    return (page_index, y0, x0)


def classify_document(doc: ExtractedDocument, *, debug: bool = False) -> list[MdElement]:
    table_bboxes = [(t.page_index, (t.x0, t.y0, t.x1, t.y1)) for t in doc.tables]
    blocks = filter_blocks_outside_tables(doc.blocks, table_bboxes)
    blocks = apply_links_to_blocks(blocks, doc.links)
    body_size = detect_body_size(blocks)
    heading_sizes = build_heading_size_map(blocks, body_size)

    if debug:
        logger.debug("body_size=%s heading_sizes=%s", body_size, heading_sizes)

    elements: list[tuple[tuple[int, float, float], MdElement]] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if not block.text.strip() and not is_code_font(block.font):
            i += 1
            continue

        if is_code_font(block.font):
            group = [block]
            j = i + 1
            blank_gap = 0
            while j < len(blocks):
                nxt = blocks[j]
                if is_code_font(nxt.font):
                    group.append(nxt)
                    blank_gap = 0
                    j += 1
                    continue
                if not nxt.text.strip() and blank_gap < 1:
                    group.append(nxt)
                    blank_gap += 1
                    j += 1
                    continue
                break
            code_text = _code_text_from_group(group)
            if code_text:
                key = _sort_key_page_y_x(block.page_index, block.y0, block.x0)
                elements.append((key, MdElement(kind=ElementKind.CODE, content=code_text)))
            i = j
            continue

        level = map_heading_level(block.size, block.font, body_size, heading_sizes)
        if level is not None:
            key = _sort_key_page_y_x(block.page_index, block.y0, block.x0)
            elements.append((key, MdElement(kind=ElementKind.HEADING, content=block.text.strip(), level=level)))
            i += 1
            continue

        text = block.text.strip()
        key = _sort_key_page_y_x(block.page_index, block.y0, block.x0)
        elements.append((key, MdElement(kind=ElementKind.PARAGRAPH, content=text)))
        i += 1

    for image in doc.images:
        filename = f"image_{image.image_index:03d}.{image.ext}"
        key = _sort_key_page_y_x(image.page_index, image.y0, image.x0)
        elements.append(
            (
                key,
                MdElement(
                    kind=ElementKind.IMAGE,
                    content=filename,
                    image_ref=None,
                ),
            )
        )

    for table in doc.tables:
        key = _sort_key_page_y_x(table.page_index, table.y0, table.x0)
        elements.append((key, MdElement(kind=ElementKind.TABLE, content=table.markdown)))

    elements.sort(key=lambda item: item[0])
    return [element for _, element in elements]
