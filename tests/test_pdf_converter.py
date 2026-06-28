from src.pdf.models import TextBlock
from src.pdf.typora_profile import (
    build_heading_size_map,
    detect_body_size,
    is_monospace_font,
    map_heading_level,
    merge_code_blocks,
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


def test_is_monospace_font_matches_common_names():
    assert is_monospace_font("Consolas") is True
    assert is_monospace_font("Courier New") is True
    assert is_monospace_font("AAABCD+Menlo-Bold") is True
    assert is_monospace_font("Source Code Pro") is True


def test_is_monospace_font_rejects_body_fonts():
    assert is_monospace_font("Times New Roman") is False
    assert is_monospace_font("Arial") is False
    assert is_monospace_font("") is False
