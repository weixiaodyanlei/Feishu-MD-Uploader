from src.pdf.models import LinkAnnotation, TextBlock
from src.pdf.typora_profile import (
    apply_links_to_blocks,
    build_heading_size_map,
    detect_body_size,
    is_monospace_font,
    map_heading_level,
    match_link_to_text,
    merge_code_blocks,
    rects_overlap,
)


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


def test_is_monospace_font_matches_common_names():
    assert is_monospace_font("Consolas") is True
    assert is_monospace_font("Courier New") is True
    assert is_monospace_font("AAABCD+Menlo-Bold") is True
    assert is_monospace_font("Source Code Pro") is True


def test_is_monospace_font_rejects_body_fonts():
    assert is_monospace_font("Times New Roman") is False
    assert is_monospace_font("Arial") is False
    assert is_monospace_font("") is False
