---
name: upload-performance-optimization-design
description: Feishu-MD-Uploader 上传性能优化设计方案，重点解决表格上传慢的问题
metadata:
  type: project
  subgroup: spec
---

# Feishu-MD-Uploader 上传性能优化设计

## 背景

当前上传 Markdown 到飞书文档时，当内容包含表格，上传速度极慢。分析发现瓶颈在于：

1. **表格单元格处理：每个单元格 3 次 API 调用**（GET 查占位符 → POST 上传内容 → DELETE 删占位符）
2. **表格行插入：逐个插入**（batch_update 不允许同一 block_id 出现多次）
3. **图片串行上传**：图片一张张上传，没有利用并发能力
4. **Block 分片上传：批次间串行**

## 优化方案

### 1. 跳过单元格 GET 查询占位符（省 60% 表格调用）

**当前行为**：每个单元格都要先 `_get_block_children_ids()` 查有几个默认占位符。
**优化后**：Feishu 新创建的空白单元格始终有 1 个占位块（空 Text），直接 hardcode `old_count=1`，跳过 GET 请求。

```python
# 旧代码
pre_child_ids = _get_block_children_ids(document_id, cell_id)
old_count = len(pre_child_ids)

# 新代码
# Feishu 新创建的空白单元格固定有 1 个空 Text 占位符
# 直接使用 hardcode 值，跳过 GET API 调用
old_count = 1
```

**风险与防御**：
- 如果 Feishu 未来改变占位符数量，会导致删除不干净
- ✅ DEBUG 模式下**第一次调用**仍发 GET 校验，将 `old_count` 与 hardcode 值对比，不一致则告警 `[WARN] 单元格占位符数量异常: expected=1, actual={n}`。首次校验通过后，后续单元格直接跳过 GET。非 DEBUG 模式下完全不发 GET。

### 2. 合并 DELETE 操作为批量删除（省 N-1 次调用）

**当前行为**：每个单元格内容上传完成后，立即 DELETE 占位符。各单元格串行，互不等待。
**优化后**：收集所有单元格的占位符删除请求，最后一次性批量请求。

```python
# 旧代码 (add_blocks 循环中)
for cell_id, old_count in cell_delete_jobs:
    _batch_delete_block_children_range(document_id, cell_id, 0, old_count)

# 新代码
# 将多个删除请求合并到一次 batch_update
def _batch_delete_many_cells(document_id, delete_jobs):
    """一次 batch_update 删除多个单元格的占位符"""
    requests = []
    for cell_id, old_count in delete_jobs:
        requests.append({
            "block_id": cell_id,
            "remove_child_blocks": {"start_index": 0, "end_index": old_count}
        })
    # 一次 PATCH 请求处理所有单元格
    ...
```

**注意**：`batch_update` 允许不同 block_id 的多个操作在同一请求中，所以可以合并。

**并发控制**：合并后的 batch 仍需处理飞书 API 频率限制（code 99991663），需保留重试+退避机制。如果单次 batch 过大（如 50+ 单元格），可拆分为多个子 batch 发送。

### 3. 创建表格时尝试直接指定完整行数

**当前行为**：限制 `row_size` 为 9，超过的再逐行插入。
**优化后**：直接按原 `row_size` 创建表格，如果 API 拒绝则回退到旧逻辑。

```python
# 移除 row_size ≤ 9 的限制，直接使用预期行数
block.table.property.row_size = table_requested_row_size
```

具体做法：先移除 `if table_requested_row_size > 9` 的限制，直接按完整行数创建。如果 `flush_batch` 返回成功（表格创建成功且有足够 cells），跳过行插入。如果创建失败（预期会收到特定错误码），再回退到 9 行创建 + 逐行插入的旧逻辑。回退在 `except` 或错误检查中完成，对用户透明。

### 4. 图片并发上传

**当前行为**：`upload_one_markdown` 循环遍历所有待上传图片，逐一调用 `image_uploader.upload_and_update_image()`。
**优化后**：使用 `concurrent.futures.ThreadPoolExecutor`，控制并发数 3-5，同时上传多张图片。

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(upload_one_image, img_info): img_info
        for img_info in pending_images
    }
    for future in as_completed(futures):
        # 处理结果
        ...
```

注意：`ImageUploader` 使用 `client` 是线程安全的（HTTP 请求级别），无需加锁。

### 5. 增大 Block chunk 到 100

**当前行为**：`chunk_size = 50`
**优化后**：`chunk_size = 100`（飞书 API 推荐上限，并发环境下可减少 50% 请求次数）

## 预期效果

| 场景 | 优化前 API 调用数 | 优化后 API 调用数 | 速度提升 |
|------|------------------|------------------|---------|
| 5行×3列表格 | ~45 次 | ~5 次 | **~9x** |
| 10行×5列表格 | ~150 次 | ~16 次 | **~9x** |
| 20行×5列表格（+插入行） | ~311 次 | ~22 次 | **~14x** |
| 10张图片的文档 | 串行 10 次 | 并发 3-4 轮 | **~3x** |
| 整体（小表格+图片） | 50-200 次 | 10-30 次 | **5-10x** |

## 涉及文件

- `src/document.py` — 跳过 GET、合并 DELETE、完整行数创建
- `src/uploader.py` — 图片并发上传、chunk_size 调大
- 无新增文件，无新增依赖

## 实施顺序

1. 跳过 GET 查询占位符（最简单的改动，效果最大）
2. 合并 DELETE 为 batch 操作
3. 尝试直接创建完整行数（带 fallback）
4. 增大 block chunk
5. 图片并发上传

每步独立可测，可随时停止。
