# Upload Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 5-10x upload speed improvement for documents with tables, and ~3x for image uploads

**Architecture:** Three independent optimizations across two files: (1) Skip unnecessary GET/DELETE API calls for table cells, merge deletes into batch; (2) Try creating tables with full row count before falling back to row-by-row insertion; (3) Parallelize image uploads and increase block batch size.

**Tech Stack:** Python 3.10+, Feishu Lark SDK, `concurrent.futures` (stdlib)

## Global Constraints

- No new third-party dependencies
- All changes must be backward-compatible (existing uploads without tables must work identically)
- Thread safety: `concurrent.futures.ThreadPoolExecutor` for image uploads
- API rate limiting: preserve retry+backoff for all Feishu API calls

---

### Task 1: Skip cell GET + batch DELETE placeholders

**Files:**
- Modify: `src/document.py:382-416`

**Problem:** For each table cell, `add_blocks` does 3 API calls: GET children → POST content → DELETE placeholder. The GET queries an invariant (Feishu always creates 1 empty Text placeholder) and the DELETE repeats per cell.

**Solution:**
- Hardcode `old_count = 1` (skip GET, save N calls per table)
- Add debug-only first-cell verification (1 GET for the whole table, only in debug mode)
- Replace per-cell DELETE loop with single `batch_update` request (all cells in one PATCH)

- [ ] **Step 1: Replace GET with hardcoded old_count + debug verification**

In `document.py`, find the cell content loop (around line 393-416). Replace:

```python
# OLD (3 API calls per cell: GET, POST, DELETE)
for i, cell_id in enumerate(cell_ids):
    if original_children and i < len(original_children):
        cell_content = original_children[i].children
        if cell_content:
            pre_child_ids = _get_block_children_ids(document_id, cell_id)
            old_count = len(pre_child_ids)
            created_in_cell = add_blocks(
                document_id,
                cell_content,
                parent_id=cell_id,
                debug=debug,
            )
            if old_count > 0 and len(created_in_cell or []) > 0:
                cell_delete_jobs.append((cell_id, old_count))
```

With:

```python
# NEW (skip GET, hardcode old_count=1; debug-only first-cell verification)
_verified_placeholder = False
for i, cell_id in enumerate(cell_ids):
    if original_children and i < len(original_children):
        cell_content = original_children[i].children
        if cell_content:
            # Feishu 新创建的空白单元格固定有 1 个空 Text 占位符
            old_count = 1

            # Debug mode: verify this assumption once per table
            if debug and not _verified_placeholder:
                actual_ids = _get_block_children_ids(document_id, cell_id)
                actual_count = len(actual_ids)
                if actual_count != old_count:
                    print(
                        f"[WARN] 单元格占位符数量异常: table={created_block.block_id}, "
                        f"cell={cell_id}, expected={old_count}, actual={actual_count}"
                    )
                _verified_placeholder = True

            # Append new blocks after Feishu defaults
            created_in_cell = add_blocks(
                document_id,
                cell_content,
                parent_id=cell_id,
                debug=debug,
            )
            if old_count > 0 and len(created_in_cell or []) > 0:
                cell_delete_jobs.append((cell_id, old_count))
```

- [ ] **Step 2: Add batch cell DELETE function**

After `_batch_delete_block_children_range` (around line 233), add a new function:

```python
def _batch_delete_cell_placeholders(document_id: str, delete_jobs: list):
    """Delete placeholder child blocks from multiple table cells in one API request."""
    if not delete_jobs:
        return
    token = _get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    requests = []
    for cell_id, old_count in delete_jobs:
        requests.append(
            {
                "block_id": cell_id,
                "remove_child_blocks": {"start_index": 0, "end_index": old_count},
            }
        )

    max_attempts = 5
    base_delay = 1.0
    retryable_http_codes = {429, 500, 502, 503, 504}
    retryable_api_codes = {99991663}

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.patch(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/batch_update",
                headers=headers,
                json={"requests": requests},
                timeout=30,
            )
        except Exception as e:
            if attempt >= max_attempts:
                raise Exception(
                    f"Failed to batch delete cell placeholders after {max_attempts} attempts: {e}"
                ) from e
            sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
            time.sleep(sleep_seconds)
            continue

        payload = {}
        try:
            payload = resp.json()
        except Exception:
            payload = {}

        api_code = payload.get("code")
        if resp.status_code < 400 and api_code == 0:
            return

        if (
            attempt < max_attempts
            and (resp.status_code in retryable_http_codes or api_code in retryable_api_codes)
        ):
            sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
            time.sleep(sleep_seconds)
            continue

        raise Exception(
            f"Failed to batch delete cell placeholders: http={resp.status_code}, "
            f"code={payload.get('code')}, msg={payload.get('msg')}"
        )
```

- [ ] **Step 3: Replace DELETE loop with single batch call**

Replace the old delete loop:

```python
for cell_id, old_count in cell_delete_jobs:
    _batch_delete_block_children_range(
        document_id,
        cell_id,
        start_index=0,
        end_index=old_count,
    )
```

With:

```python
# Single batch_update call for all cells
_batch_delete_cell_placeholders(document_id, cell_delete_jobs)
```

- [ ] **Step 4: Verify and commit**

```bash
cd D:/code/Github/Feishu-MD-Uploader
python -c "import src.document; print('import OK')"
pip install flake8 && python -m flake8 src/document.py --max-line-length=110
git add src/document.py
git commit -m "perf: skip cell GET query and batch cell placeholder deletes"
```

---

### Task 2: Try full row_size table creation

**Files:**
- Modify: `src/document.py:339-348` and `src/document.py:377-388`

**Problem:** Current code caps table creation at 9 rows (`if table_requested_row_size > 9: block.table.property.row_size = 9`), then inserts extra rows one-by-one. The API may now support >9 rows.

**Solution:** Remove the cap. If the created table's cells match expected count, we're done. If fewer cells were created (API still enforces a limit), fall back to row insertion for the remainder.

- [ ] **Step 1: Remove row_size cap**

Find around line 339-348:

```python
table_requested_row_size = None
if (
    block.block_type == 31 and
    block.table and
    block.table.property and
    block.table.property.row_size
):
    table_requested_row_size = block.table.property.row_size
    # Feishu create block API accepts at most 9 rows for table.
    if table_requested_row_size > 9:
        block.table.property.row_size = 9
```

Replace with:

```python
table_requested_row_size = None
column_size = None
if (
    block.block_type == 31 and
    block.table and
    block.table.property and
    block.table.property.row_size
):
    table_requested_row_size = block.table.property.row_size
    column_size = block.table.property.column_size
    # 不再限制为 9 行——API 可能已支持更多行数
    # 如果创建后 cell 数量不够，会触发 fallback 插入行
```

- [ ] **Step 2: Update cell count check to be dynamic**

Find around line 377-388:

```python
if block.block_type == 31: # Table Special Handling
    if not created_block.table or not created_block.table.cells:
        print("Warning: Created table has no cells")
        continue

    cell_ids = created_block.table.cells
    if table_requested_row_size and table_requested_row_size > 9:
        extra_rows = table_requested_row_size - 9
        _batch_insert_table_rows(document_id, created_block.block_id, extra_rows)
        fetched_cell_ids = _get_table_cell_ids(document_id, created_block.block_id)
        if fetched_cell_ids:
            cell_ids = fetched_cell_ids
```

Replace with:

```python
if block.block_type == 31:  # Table Special Handling
    if not created_block.table or not created_block.table.cells:
        print("Warning: Created table has no cells")
        continue

    cell_ids = created_block.table.cells

    # 动态计算：如果 API 创建了全部行，跳过插入；否则 fallback 插入额外行
    if table_requested_row_size and column_size:
        expected_cell_count = table_requested_row_size * column_size
        actual_cell_count = len(cell_ids)
        if actual_cell_count < expected_cell_count:
            extra_rows = (expected_cell_count - actual_cell_count) // column_size
            if extra_rows > 0:
                _batch_insert_table_rows(
                    document_id, created_block.block_id, extra_rows
                )
                fetched_cell_ids = _get_table_cell_ids(
                    document_id, created_block.block_id
                )
                if fetched_cell_ids:
                    cell_ids = fetched_cell_ids
```

- [ ] **Step 3: Verify and commit**

```bash
cd D:/code/Github/Feishu-MD-Uploader
python -c "import src.document; print('import OK')"
python -m flake8 src/document.py --max-line-length=110
git add src/document.py
git commit -m "perf: try full row_size table creation with dynamic fallback"
```

---

### Task 3: Concurrent image upload + larger block chunk

**Files:**
- Modify: `src/uploader.py`

**Problem:** Images upload sequentially (one at a time), wasting network latency. Block chunk size is conservative at 50.

**Solution:** Use `ThreadPoolExecutor(max_workers=3)` for image uploads. Increase `chunk_size` to 100. Extract per-image upload logic into a helper function.

- [ ] **Step 1: Increase block chunk size**

In `uploader.py`, line 97:

```python
chunk_size = 50
```

Change to:

```python
chunk_size = 100
```

- [ ] **Step 2: Extract image upload into helper function**

Before `upload_one_markdown`, add:

```python
def _upload_image_and_update_block(
    img_info: dict,
    markdown_dir: str,
    client,
    doc_token: str,
    block_id_map: list,
    debug: bool = False,
) -> bool:
    """Download (if URL) a single image and upload it to its block. Returns True on success."""
    block_index = img_info["block_index"]
    image_path = img_info["image_path"]
    temp_file_path = None

    if image_path.startswith(("http://", "https://")):
        if debug:
            print(f"   - Downloading image: {image_path}")
        try:
            response = requests.get(
                image_path,
                stream=True,
                timeout=60,
                headers=_IMAGE_DOWNLOAD_HEADERS,
            )
            response.raise_for_status()

            path_part = urlparse(image_path).path
            suffix = os.path.splitext(path_part)[1].lower()
            allowed = (
                ".png", ".jpg", ".jpeg", ".gif", ".webp",
                ".bmp", ".heic", ".tif", ".tiff",
            )
            if suffix not in allowed:
                ct = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if "webp" in ct:
                    suffix = ".webp"
                elif "jpeg" in ct or "jpg" in ct:
                    suffix = ".jpg"
                elif "png" in ct:
                    suffix = ".png"
                else:
                    suffix = ".webp"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                temp_file_path = tmp.name
                image_path = temp_file_path

        except Exception as e:
            if debug:
                print(f"     ❌ Failed to download image: {e}")
            return False
    else:
        if not os.path.isabs(image_path):
            image_path = os.path.join(markdown_dir, image_path)

    if block_index < len(block_id_map):
        block_id = block_id_map[block_index]
        if debug:
            print(f"   - Uploading image: {os.path.basename(image_path)} to block")
        image_uploader = ImageUploader(client)
        success = image_uploader.upload_and_update_image(
            image_path, doc_token, block_id
        )
        if debug:
            if success:
                print("     ✅ Image uploaded and set")
            else:
                print("     ❌ Failed to upload image")
    else:
        success = False

    if temp_file_path and os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    return success
```

- [ ] **Step 3: Replace sequential image loop with concurrent upload**

Find the sequential loop (around lines 126-206, from `if pending_images:` to the end of the image handling block). Replace the entire block:

**注意保留** `from concurrent.futures import ThreadPoolExecutor, as_completed` 在文件顶部（如果还没有的话，需要加在文件头部的 import 区域）。

```python
pending_images = md_parser.get_pending_images()
if pending_images:
    success_count = 0
    fail_count = 0

    if TQDM_AVAILABLE and not debug:
        print(f"🖼️  Uploading {len(pending_images)} images (3 concurrent)...")
        pbar = tqdm(total=len(pending_images), desc="Images", unit="img", ncols=80)
    else:
        pbar = None
        if debug:
            print(f"Uploading {len(pending_images)} images (3 concurrent)...")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _upload_image_and_update_block,
                img_info,
                markdown_dir,
                client,
                doc_token,
                block_id_map,
                debug,
            ): img_info
            for img_info in pending_images
        }

        for future in as_completed(futures):
            try:
                if future.result():
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                if debug:
                    img_info = futures[future]
                    print(f"     ❌ Image upload failed: {img_info.get('image_path', '?')} — {e}")
            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()
    msg = "✅ Images processed."
    if fail_count:
        msg += f" ({success_count} success, {fail_count} failed)"
    print(msg)
```

- [ ] **Step 4: Add ThreadPoolExecutor import**

Check if `concurrent.futures` is already imported at the top of `uploader.py`. If not, add to the import section:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

- [ ] **Step 5: Verify and commit**

```bash
cd D:/code/Github/Feishu-MD-Uploader
python -c "import src.uploader; print('import OK')"
python -m flake8 src/uploader.py --max-line-length=110
git add src/uploader.py
git commit -m "perf: concurrent image upload (ThreadPool:3) and larger block chunk (100)"
```

---

## Verification

After all tasks are committed, run a functional test:

```bash
cd D:/code/Github/Feishu-MD-Uploader
python src/uploader.py tests/fixtures/test_document.md --debug
```

Expected result:
- Document created successfully
- Table cells populated correctly (no placeholder artifacts)
- Images uploaded (concurrent, 3 at a time)
- Overall upload time significantly reduced

Compare with a baseline on the same document before changes if desired.
