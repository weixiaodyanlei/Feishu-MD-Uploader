"""
Pre-parse hooks for Markdown by source type (platform-specific conventions).

Types:
  1 — 腾讯云开发者
  2 — 腾讯技术工程
  3 — 阿里云开发者
"""
from __future__ import annotations

import re
from typing import Optional

# Source type ids (CLI --type)
SOURCE_TENCENT_CLOUD_DEVELOPER = 1
SOURCE_TENCENT_TECH_ENGINEERING = 2
SOURCE_ALIYUN_DEVELOPER = 3

SOURCE_TYPE_NAMES = {
    SOURCE_TENCENT_CLOUD_DEVELOPER: "腾讯云开发者",
    SOURCE_TENCENT_TECH_ENGINEERING: "腾讯技术工程",
    SOURCE_ALIYUN_DEVELOPER: "阿里云开发者",
}


def _hook_tencent_tech_engine_headings(markdown: str) -> str:
    """
    Map ATX headings per line: ##### -> ###, #### -> ##, ### -> #.
    Only lines that are exactly h5 / h4 / h3 (not h6+) are rewritten.
    """
    out_lines = []
    for raw in markdown.split("\n"):
        line = raw.rstrip("\r")
        if re.match(r"^#{5}\s", line):
            line = re.sub(r"^#{5}\s", "### ", line, count=1)
        elif re.match(r"^#{4}\s", line):
            line = re.sub(r"^#{4}\s", "## ", line, count=1)
        elif re.match(r"^#{3}\s", line):
            line = re.sub(r"^#{3}\s", "# ", line, count=1)
        out_lines.append(line)
    return "\n".join(out_lines)


def apply_preprocess_hooks(markdown: str, source_type: Optional[int]) -> str:
    """Run type-specific text transforms before markdown-it tokenization."""
    if source_type is None:
        return markdown
    if source_type == SOURCE_TENCENT_TECH_ENGINEERING:
        return _hook_tencent_tech_engine_headings(markdown)
    return markdown
