---
name: pdf-to-md-design
description: Typora 类文本 PDF 转 Markdown 独立 CLI 设计方案
metadata:
  type: project
  subgroup: spec
---

# PDF 转 Markdown 设计

## 背景与目标

Feishu-MD-Uploader 当前流程为 `Markdown → 飞书 Docx`。用户需要将 **Typora / MarkText 等编辑器从 Markdown 导出的文本型 PDF** 还原为 Markdown，作为上传前的预处理步骤。

**集成方式：** 独立 CLI（方案 A），不自动串联 `uploader.py`。

**必须保留的结构（优先级）：**

| 优先级 | 元素 |
|--------|------|
| 必须 | 标题层级（`#` / `##` / `###`） |
| 必须 | 代码块（等宽字体区域 → ` ``` `） |
| 必须 | 链接（PDF 超链接注解 → `[text](uri)`） |
| 必须 | 图片（提取为本地文件，MD 相对路径引用） |
| 尽力 | 有序/无序列表（行首模式匹配） |
| 不做 | 表格 MD 化、行内粗斜体还原、OCR、批量转换 |

**PDF 来源假设：** Typora / MarkText「导出 PDF」。本质是 HTML 渲染后打印，保留字号层级、等宽字体、链接注解和内嵌图片。

## 方案选型

评估三种方案后选用 **PyMuPDF 自定义解析流水线**：

| 方案 | 说明 | 结论 |
|------|------|------|
| PyMuPDF 自定义流水线 | 提取文本+字体+链接+图片，Typora 启发式组装 MD | **采用** |
| pymupdf4llm 一键转 MD | 黑盒输出，难精确控制 A/B/D/E | 不采用 |
| pdfplumber + PyMuPDF | 布局分析强，但 Typora 单栏 PDF 过重 | 不采用 |

## 架构

### 模块划分

```
pdf_to_md.py              # CLI 入口（argparse）
src/pdf/
  __init__.py
  extractor.py            # PyMuPDF：文本块、链接、图片
  typora_profile.py       # Typora 启发式：标题/代码/段落/图片分类
  markdown_writer.py      # 组装最终 MD 字符串
```

### 数据流

```
PDF 文件
  → extractor：提取 raw blocks（文本+字体+坐标）、links、images
  → typora_profile：分类为 heading / code / paragraph / image
  → markdown_writer：输出 article.md + {name}_assets/*.png
```

### CLI 接口

```bash
python pdf_to_md.py input.pdf                         # 输出 input.md
python pdf_to_md.py input.pdf -o output.md            # 指定输出路径
python pdf_to_md.py input.pdf --assets-dir imgs       # 自定义图片目录名
python pdf_to_md.py input.pdf --no-overwrite          # 输出已存在则拒绝
python pdf_to_md.py input.pdf --clean-assets          # 清空 assets 后重建
python pdf_to_md.py input.pdf --debug                 # 详细日志
```

**与上传器配合（手动两步）：**

```bash
python pdf_to_md.py blog/article.pdf
python src/uploader.py blog/article.md --title "My Blog Post"
```

## Typora 启发式规则

### 文本块提取（extractor.py）

使用 PyMuPDF `page.get_text("dict")` 获取 span 级信息：文本、`font`、`size`、`flags`（粗体等）、边界框 `(x0, y0, x1, y1)`。

- 同一行内相邻 span（字号相同、y 坐标接近）合并为 **line**
- 相邻 line 若字体/字号一致且行距正常，合并为 **block**

### 标题识别

1. 统计正文字号：出现次数最多的非等宽字号 → `body_size`
2. 将所有 **大于 body_size** 且 **非等宽** 的字号去重排序，映射标题层级：
   - 最大 → `#`
   - 次大 → `##`
   - 再次 → `###`
   - 更大字号（h4+）→ 统一降为 `###`
3. 粗体（`flags & 16`）作为辅助信号，不单独判定标题

### 代码块识别

**判定：** 字体名匹配等宽集合（不区分大小写）：

`Consolas`, `Courier`, `Courier New`, `Menlo`, `Monaco`, `Source Code Pro`, `monospace`

**合并：** 连续多个等宽 block（块间空行 ≤ 1 行）合并为一个代码块；块内缩进保留。

**语言标签：** 初版不猜测，统一输出无语言标识的 ` ``` `。

**行内代码：** 初版不专门处理。

### 链接还原

1. `page.get_links()` 获取 `{uri, rect}` 注解
2. 对每个 link rect，找与之重叠或最近的 text span
3. 输出 `[链接文本](uri)`
4. 同一 span 多个链接 → 取第一个 URI
5. 无法匹配文本 → 降级为裸 URL 段落

### 图片提取

1. `page.get_images()` + `doc.extract_image(xref)` 提取二进制
2. 用图片 bbox 参与阅读顺序排序
3. 保存到 `{输出文件名}_assets/image_{序号:03d}.{ext}`
4. MD 引用：`![image_001](article_assets/image_001.png)`

### 其余内容

| 类型 | 策略 |
|------|------|
| 普通段落 | 非标题、非等宽 → 合并为段落，段间 `\n\n` |
| 无序列表 | 行首匹配 `^[-*+•]\s` → 保留 `- ` 前缀 |
| 有序列表 | 行首匹配 `^\d+\.\s` → 原样保留 |
| 粗体/斜体 | 不还原 |
| 表格 | 输出为纯文本行 |

### 阅读顺序

所有元素（text block、image）按 `(page_index, y0, x0)` 排序。初版不处理多栏布局。

## 错误处理

| 场景 | 行为 |
|------|------|
| PDF 不存在 / 无法打开 | 退出码 `1`，stderr 明确错误 |
| 加密 PDF | 退出码 `1`，提示不支持 |
| 无可提取文本（扫描件） | 退出码 `2`，提示仅支持文本型 PDF |
| 单张图片提取失败 | 警告，跳过，继续 |
| 链接无法匹配文本 | 降级裸 URL，`--debug` 时详情 |
| 输出已存在 | 默认覆盖；`--no-overwrite` 拒绝 |
| assets 目录已存在 | 默认复用并追加序号；`--clean-assets` 清空重建 |

**日志：** 默认输出进度摘要；`--debug` 输出字体统计、标题映射、跳过元素详情。

## 依赖

`requirements.txt` 追加：

```
PyMuPDF>=1.24.0
```

不引入 pdfplumber、pymupdf4llm、OCR 库。图片保存优先 PyMuPDF `extract_image`，必要时用已有 Pillow 做格式转换。

## 测试

### 单元测试（`tests/test_pdf_converter.py`）

- `is_monospace_font()` — 字体名判定
- `map_heading_level()` — 字号 → `#` 映射
- `merge_code_blocks()` — 连续等宽块合并
- `match_link_to_text()` — link rect 与 span 匹配

使用 mock dict 数据，不依赖真实 PDF。

### 集成测试（可选）

在 `tests/fixtures/` 放置 Typora 导出的小型 PDF；断言输出含标题、代码块、链接、图片引用。初版以单元测试为主；CI 无法生成 fixture 时在 README 说明本地补充方式。

## 实现文件清单

| 文件 | 说明 |
|------|------|
| `pdf_to_md.py` | CLI 入口 |
| `src/pdf/extractor.py` | PyMuPDF 提取 |
| `src/pdf/typora_profile.py` | Typora 启发式分类 |
| `src/pdf/markdown_writer.py` | MD 组装 |
| `src/pdf/__init__.py` | 包标识 |
| `tests/test_pdf_converter.py` | 单元测试 |
| `requirements.txt` | 追加 PyMuPDF |
| `README.md` | 新增「PDF 转 Markdown」小节 |

## 刻意不做（YAGNI）

- 批量转换多 PDF
- OCR / 扫描件支持
- 与 `uploader.py` 自动串联
- 非 Typora profile（MarkText 兼容通过同一启发式，不单独分支）
- 表格 MD 化、行内格式还原、代码语言猜测
