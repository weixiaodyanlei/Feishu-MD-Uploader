from pathlib import Path

from src.pdf.extractor import merge_adjacent_line_blocks, merge_spans_to_blocks, _bbox_to_tuple
from src.pdf.models import ElementKind, ExtractedDocument, ExtractedImage, LinkAnnotation, MdElement, TextBlock
from src.pdf.typora_profile import (
    apply_links_to_blocks,
    build_heading_size_map,
    classify_document,
    detect_body_size,
    is_code_font,
    is_monospace_font,
    map_heading_level,
    match_link_to_text,
    merge_code_blocks,
    rects_overlap,
    _code_text_from_group,
    _is_line_number_gutter,
)
from src.pdf.markdown_writer import render_markdown, save_images


def _block(size: float, font: str = "Arial", text: str = "x") -> TextBlock:
    return TextBlock(
        text=text,
        font=font,
        size=size,
        flags=0,
        page_index=0,
        x0=0,
        y0=0,
        x1=10,
        y1=10,
    )


def test_is_monospace_font_matches_common_names():
    assert is_monospace_font("Consolas") is True
    assert is_monospace_font("Courier New") is True
    assert is_monospace_font("AAABCD+Menlo-Bold") is True
    assert is_monospace_font("Source Code Pro") is True
    assert is_code_font("LucidaConsole") is True
    assert is_code_font("LucidaConsole-Bold") is True


def test_is_monospace_font_rejects_body_fonts():
    assert is_monospace_font("Times New Roman") is False
    assert is_monospace_font("Arial") is False
    assert is_monospace_font("") is False


def test_detect_body_size_picks_most_common_non_monospace():
    blocks = [_block(11.0)] * 5 + [_block(18.0, text="Title")] * 1 + [_block(11.0, font="Consolas")] * 2
    assert detect_body_size(blocks) == 11.0


def test_map_heading_level_maps_largest_three_sizes():
    body = 11.0
    heading_sizes = build_heading_size_map(
        [_block(24.0), _block(18.0), _block(14.0), _block(11.0)],
        body,
    )
    assert heading_sizes == [24.0, 18.0, 14.0]
    assert map_heading_level(24.0, "Arial", body, heading_sizes) == 1
    assert map_heading_level(18.0, "Arial", body, heading_sizes) == 2
    assert map_heading_level(14.0, "Arial", body, heading_sizes) == 3
    assert map_heading_level(13.0, "Arial", body, heading_sizes) == 3
    assert map_heading_level(11.0, "Arial", body, heading_sizes) is None
    assert map_heading_level(11.0, "Consolas", body, heading_sizes) is None


def test_merge_code_blocks_groups_consecutive_monospace():
    blocks = [
        _block(10.0, font="Consolas", text="line1"),
        _block(10.0, font="Consolas", text="line2"),
        _block(11.0, font="Arial", text="paragraph"),
        _block(10.0, font="Menlo", text="code2"),
    ]
    groups = merge_code_blocks(blocks)
    assert len(groups) == 2
    assert [b.text for b in groups[0]] == ["line1", "line2"]
    assert [b.text for b in groups[1]] == ["code2"]


def test_merge_code_blocks_allows_one_blank_gap():
    blocks = [
        _block(10.0, font="Consolas", text="a"),
        TextBlock("", "Consolas", 10.0, 0, 0, 0, 0, 10, 10),
        _block(10.0, font="Consolas", text="b"),
    ]
    groups = merge_code_blocks(blocks)
    assert len(groups) == 1
    assert [b.text for b in groups[0]] == ["a", "", "b"]


def test_rects_overlap_detects_intersection():
    assert rects_overlap((0, 0, 10, 10), (5, 5, 15, 15)) is True
    assert rects_overlap((0, 0, 10, 10), (20, 20, 30, 30)) is False


def test_match_link_to_text_finds_overlapping_block():
    blocks = [
        TextBlock(
            text="click here",
            font="Arial",
            size=11.0,
            flags=0,
            page_index=0,
            x0=10,
            y0=10,
            x1=80,
            y1=20,
        )
    ]
    link = LinkAnnotation(
        uri="https://example.com",
        page_index=0,
        x0=12,
        y0=11,
        x1=70,
        y1=19,
    )
    assert match_link_to_text(link, blocks) == "click here"


def test_apply_links_to_blocks_rewrites_markdown_link():
    block = TextBlock(
        text="docs",
        font="Arial",
        size=11.0,
        flags=0,
        page_index=0,
        x0=0,
        y0=0,
        x1=40,
        y1=10,
    )
    link = LinkAnnotation(uri="https://docs.example.com", page_index=0, x0=1, y0=1, x1=39, y1=9)
    updated = apply_links_to_blocks([block], [link])
    assert updated[0].text == "[docs](https://docs.example.com)"


def test_merge_spans_to_blocks_combines_same_line_spans():
    page_dict = {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            {
                                "text": "Hello ",
                                "font": "Arial",
                                "size": 11.0,
                                "flags": 0,
                                "bbox": [0, 0, 20, 10],
                            },
                            {
                                "text": "World",
                                "font": "Arial",
                                "size": 11.0,
                                "flags": 0,
                                "bbox": [20, 0, 50, 10],
                            },
                        ]
                    }
                ],
            }
        ]
    }
    blocks = merge_spans_to_blocks(page_dict, page_index=0)
    assert len(blocks) == 1
    assert blocks[0].text == "Hello World"
    assert blocks[0].size == 11.0


def test_bbox_to_tuple_accepts_tuple_and_rect_like():
    assert _bbox_to_tuple((1.0, 2.0, 3.0, 4.0)) == (1.0, 2.0, 3.0, 4.0)

    class Rect:
        x0, y0, x1, y1 = 5.0, 6.0, 7.0, 8.0

    assert _bbox_to_tuple(Rect()) == (5.0, 6.0, 7.0, 8.0)


def test_merge_adjacent_line_blocks_combines_paragraph_lines():
    blocks = [
        TextBlock("Hello", "Arial", 11.0, 0, 0, 0, 0, 10, 10),
        TextBlock("world.", "Arial", 11.0, 0, 0, 0, 12, 10, 22),
    ]
    merged = merge_adjacent_line_blocks(blocks)
    assert len(merged) == 1
    assert merged[0].text == "Hello world."


def test_merge_adjacent_line_blocks_keeps_code_lines_separate():
    blocks = [
        TextBlock("import os", "LucidaConsole", 8.78, 0, 0, 115, 0, 10, 125),
        TextBlock("print('hi')", "LucidaConsole", 8.78, 0, 0, 125, 0, 10, 135),
    ]
    merged = merge_adjacent_line_blocks(blocks)
    assert len(merged) == 2
    assert merged[0].text == "import os"
    assert merged[1].text == "print('hi')"


def test_code_text_from_group_strips_line_number_gutter():
    group = [
        TextBlock("1", "LucidaConsole", 8.78, 0, 0, 88, 0, 10, 98),
        TextBlock("conda create -n test", "LucidaConsole", 8.78, 0, 0, 115, 0, 10, 125),
        TextBlock("2", "LucidaConsole", 8.78, 0, 0, 88, 0, 10, 135),
        TextBlock("conda activate test", "LucidaConsole", 8.78, 0, 0, 115, 0, 10, 145),
    ]
    assert _is_line_number_gutter(group[0]) is True
    assert _code_text_from_group(group) == "conda create -n test\nconda activate test"

def test_apply_links_to_blocks_falls_back_to_bare_url():
    block = TextBlock("body", "Arial", 11.0, 0, 0, 0, 0, 10, 10)
    link = LinkAnnotation("https://orphan.example.com", 0, 100, 100, 110, 110)
    updated = apply_links_to_blocks([block], [link])
    assert updated[-1].text == "https://orphan.example.com"


def test_classify_document_orders_heading_code_paragraph_and_image():
    doc = ExtractedDocument(
        blocks=[
            TextBlock(
                text="Title",
                font="Arial",
                size=24.0,
                flags=0,
                page_index=0,
                x0=0,
                y0=0,
                x1=50,
                y1=20,
            ),
            TextBlock(
                text="Intro paragraph",
                font="Arial",
                size=11.0,
                flags=0,
                page_index=0,
                x0=0,
                y0=30,
                x1=80,
                y1=40,
            ),
            TextBlock(
                text="More body text",
                font="Arial",
                size=11.0,
                flags=0,
                page_index=0,
                x0=0,
                y0=35,
                x1=80,
                y1=45,
            ),
            TextBlock(
                text="print('hi')",
                font="Consolas",
                size=10.0,
                flags=0,
                page_index=0,
                x0=0,
                y0=50,
                x1=80,
                y1=60,
            ),
        ],
        links=[],
        images=[
            ExtractedImage(
                page_index=0,
                x0=0,
                y0=100,
                xref=1,
                ext="png",
                data=b"\x89PNG",
                image_index=1,
            )
        ],
    )

    elements = classify_document(doc)
    kinds = [e.kind for e in elements]
    assert kinds[0] == ElementKind.HEADING
    assert ElementKind.PARAGRAPH in kinds
    assert kinds[-1] == ElementKind.IMAGE
    assert any(e.kind == ElementKind.CODE and e.content == "print('hi')" for e in elements)
    assert elements[0].level == 1


def test_render_markdown_formats_all_element_kinds():
    md = render_markdown(
        [
            MdElement(kind=ElementKind.HEADING, content="Title", level=1),
            MdElement(kind=ElementKind.PARAGRAPH, content="Hello"),
            MdElement(kind=ElementKind.TABLE, content="| A | B |\n| --- | --- |\n| 1 | 2 |"),
            MdElement(kind=ElementKind.CODE, content="x = 1"),
            MdElement(
                kind=ElementKind.IMAGE,
                content="image_001.png",
                image_ref="my_assets/image_001.png",
            ),
        ],
        assets_dir_name="my_assets",
    )
    assert "# Title" in md
    assert "Hello" in md
    assert "| A | B |" in md
    assert "```" in md and "x = 1" in md
    assert "![image_001](my_assets/image_001.png)" in md


def test_save_images_writes_files(tmp_path: Path):
    images = [
        ExtractedImage(
            page_index=0,
            x0=0,
            y0=0,
            xref=1,
            ext="png",
            data=b"PNGDATA",
            image_index=1,
        )
    ]
    assets_dir = tmp_path / "article_assets"
    save_images(images, assets_dir)
    assert (assets_dir / "image_001.png").read_bytes() == b"PNGDATA"


def test_normalize_table_rows_from_sparse_grid():
    raw = [
        [None, None, "平台", None, "网址"],
        [None, "OpenRouter", None, "https://example.com", None],
    ]
    from src.pdf.table_utils import normalize_table_rows, table_to_markdown

    rows = normalize_table_rows(raw)
    assert rows == [["平台", "网址"], ["OpenRouter", "https://example.com"]]
    md = table_to_markdown(rows)
    assert md.startswith("| 平台 | 网址 |")
