from __future__ import annotations

import re
from typing import Iterable

from src.pdf.models import TextBlock


def _clean_cell(value) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s*\n\s*", " ", str(value).strip())
    return text.replace("|", "\\|")


def _sparse_rows(raw_rows: list[list]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in raw_rows:
        cells = [_clean_cell(c) for c in row if c is not None and _clean_cell(c)]
        if cells:
            rows.append(cells)
    return rows


def normalize_table_rows(raw_rows: list[list]) -> list[list[str]] | None:
    """Collapse sparse PDF table grids into consistent row widths."""
    rows = _sparse_rows(raw_rows)
    if len(rows) < 2:
        return None

    col_counts: dict[int, int] = {}
    for row in rows:
        col_counts[len(row)] = col_counts.get(len(row), 0) + 1
    target_cols = max(col_counts, key=lambda n: (col_counts[n], n))
    if target_cols < 2:
        return None

    normalized: list[list[str]] = []
    for row in rows:
        if len(row) == target_cols:
            normalized.append(row)
        elif len(row) > target_cols:
            normalized.append(row[:target_cols])
        elif len(row) == 1:
            # Orphan fragment from merged PDF cells — skip.
            continue
        else:
            normalized.append(row + [""] * (target_cols - len(row)))

    return normalized if len(normalized) >= 2 else None


def table_to_markdown(rows: list[list[str]]) -> str:
    ncol = max(len(r) for r in rows)
    padded = [row + [""] * (ncol - len(row)) for row in rows]
    lines = [
        "| " + " | ".join(padded[0]) + " |",
        "| " + " | ".join(["---"] * ncol) + " |",
    ]
    for row in padded[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def is_valid_table(rows: list[list[str]], bbox: tuple[float, float, float, float]) -> bool:
    if len(rows) < 2 or max(len(r) for r in rows) < 2:
        return False
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    if width < 80 or height < 24:
        return False
    non_empty_cells = sum(1 for row in rows for cell in row if cell.strip())
    return non_empty_cells >= 4


def block_inside_table(block: TextBlock, bbox: tuple[float, float, float, float]) -> bool:
    cx = (block.x0 + block.x1) / 2
    cy = (block.y0 + block.y1) / 2
    x0, y0, x1, y1 = bbox
    return x0 <= cx <= x1 and y0 <= cy <= y1


def filter_blocks_outside_tables(
    blocks: Iterable[TextBlock],
    table_bboxes: list[tuple[int, tuple[float, float, float, float]]],
) -> list[TextBlock]:
    if not table_bboxes:
        return list(blocks)
    kept: list[TextBlock] = []
    for block in blocks:
        if any(
            page_index == block.page_index and block_inside_table(block, bbox)
            for page_index, bbox in table_bboxes
        ):
            continue
        kept.append(block)
    return kept
