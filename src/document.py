import json
import random
import time
import requests
import lark_oapi as lark
from lark_oapi.api.docx.v1.model import *
from lark_oapi.api.drive.v1.model import *
from .auth import get_client
from .config import Config

def _to_serializable(obj):
    """Convert SDK models/objects to JSON-serializable structures recursively."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _to_serializable(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in vars(obj).items():
            if key.startswith("_") or callable(value):
                continue
            result[key] = _to_serializable(value)
        return result
    return str(obj)

def create_document(title: str, folder_token: str = None) -> str:
    """
    Create a new Docx document.
    Returns the document token.
    """
    client = get_client()
    
    # Construct request
    request = CreateDocumentRequest.builder() \
        .request_body(CreateDocumentRequestBody.builder()
            .folder_token(folder_token)
            .title(title)
            .build()) \
        .build()

    # Send request
    response = client.docx.v1.document.create(request)

    if not response.success():
        raise Exception(f"Failed to create document: {response.code}, {response.msg}, {response.error}")

    return response.data.document.document_id

def add_blocks(
    document_id: str,
    blocks: list,
    parent_id: str = None,
    insert_index: int = None,
    debug: bool = False
):
    """
    Add blocks to the document or a specific parent block.
    Handles Table blocks by creating them empty first and then populating cells.
    """
    if parent_id is None:
        parent_id = document_id
        
    client = get_client()

    def _get_tenant_access_token() -> str:
        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": Config.APP_ID, "app_secret": Config.APP_SECRET},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise Exception(f"Failed to get tenant access token: {payload}")
        return payload.get("tenant_access_token")

    def _batch_insert_table_rows(document_id: str, table_block_id: str, row_count: int):
        if row_count <= 0:
            return
        token = _get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        # Important: batch_update does NOT allow duplicated block_id in one request.
        # So we must insert one row per request for the same table block.
        max_attempts = 5
        base_delay = 1.0
        retryable_http_codes = {429, 500, 502, 503, 504}
        retryable_api_codes = {99991663}  # too many requests

        for _ in range(row_count):
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = requests.patch(
                        f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/batch_update",
                        headers=headers,
                        json={
                            "requests": [
                                {"block_id": table_block_id, "insert_table_row": {"row_index": -1}}
                            ]
                        },
                        timeout=30,
                    )
                except Exception as e:
                    if attempt >= max_attempts:
                        raise Exception(
                            f"Failed to insert table row after {max_attempts} attempts: {e}"
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
                    break

                if (
                    attempt < max_attempts and
                    (resp.status_code in retryable_http_codes or api_code in retryable_api_codes)
                ):
                    sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)
                    continue

                raise Exception(
                    f"Failed to insert table row: http={resp.status_code}, "
                    f"code={payload.get('code')}, msg={payload.get('msg')}, "
                    f"error={payload.get('error')}"
                )

    def _get_table_cell_ids(document_id: str, table_block_id: str) -> list:
        token = _get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{table_block_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise Exception(
                f"Failed to fetch table block: {payload.get('code')}, "
                f"{payload.get('msg')}, {payload.get('error')}"
            )
        block = payload.get("data", {}).get("block", {})
        table = block.get("table", {})
        cells = table.get("cells", [])
        return cells or []

    def _get_block_children_ids(document_id: str, parent_block_id: str) -> list:
        """Return direct child block_id list for any parent block (e.g. table cell)."""
        token = _get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise Exception(
                f"Failed to fetch block children: {payload.get('code')}, "
                f"{payload.get('msg')}, {payload.get('error')}"
            )
        block = payload.get("data", {}).get("block", {})
        return block.get("children") or []

    def _batch_delete_block_children_range(
        document_id: str, parent_block_id: str, start_index: int, end_index: int
    ):
        """Delete child blocks in [start_index, end_index) under parent_block_id."""
        if start_index >= end_index:
            return
        token = _get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        max_attempts = 5
        base_delay = 1.0
        retryable_http_codes = {429, 500, 502, 503, 504}
        retryable_api_codes = {99991663}

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.delete(
                    f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/"
                    f"{parent_block_id}/children/batch_delete?document_revision_id=-1",
                    headers=headers,
                    json={"start_index": start_index, "end_index": end_index},
                    timeout=30,
                )
            except Exception as e:
                if attempt >= max_attempts:
                    raise Exception(
                        f"Failed to delete block children after {max_attempts} attempts: {e}"
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
                f"Failed to delete block children: http={resp.status_code}, "
                f"code={payload.get('code')}, msg={payload.get('msg')}, "
                f"error={payload.get('error')}"
            )

    def _is_text_block(block) -> bool:
        """Check if block is a TEXT block with simple content (no nested children)."""
        return getattr(block, 'block_type', None) == 2 and not getattr(block, 'children', None)

    def _create_table_via_descendant(
        document_id: str, parent_block_id: str, table_block,
        cell_contents_list: list, row_size: int, column_size: int, debug: bool,
    ):
        """
        Create a table with pre-populated content via the descendant API.
        Simple-text cells are pre-populated inline; complex cells get an
        empty placeholder (caller must handle append+delete for those).

        Returns (created_table_block, complex_cell_indices) on success.
        Raises on failure.
        """
        import random

        token = _get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        tid = f"_dt_{random.randint(100000, 999999)}"
        header_row = False
        if table_block.table and table_block.table.property:
            header_row = getattr(table_block.table.property, 'header_row', False)

        descendants = []
        cell_temp_ids = []
        complex_cell_indices = []
        max_attempts = 5
        base_delay = 1.0
        retryable_codes = {429, 500, 502, 503, 504}
        retryable_api_codes = {99991663}

        for i, cell_block in enumerate(cell_contents_list):
            cell_content = cell_block.children if cell_block else []
            cell_tid = f"{tid}_c{i}"
            cell_temp_ids.append(cell_tid)

            if not cell_content:
                # Empty cell: empty Text placeholder
                placeholder_tid = f"{cell_tid}_p"
                descendants.append({
                    "block_id": cell_tid, "block_type": 32,
                    "table_cell": {}, "children": [placeholder_tid],
                })
                descendants.append({
                    "block_id": placeholder_tid, "block_type": 2,
                    "text": {"elements": [{"text_run": {"content": ""}}]},
                    "children": [],
                })
            elif all(_is_text_block(b) for b in cell_content):
                # Simple text: pre-populate inline
                text_tids = []
                for j, tb in enumerate(cell_content):
                    txt_id = f"{cell_tid}_t{j}"
                    text_tids.append(txt_id)
                    text_obj = getattr(tb, 'text', None)
                    elements = []
                    if text_obj and getattr(text_obj, 'elements', None):
                        for el in text_obj.elements:
                            tr = getattr(el, 'text_run', None)
                            if tr:
                                elements.append({
                                    "text_run": {"content": getattr(tr, 'content', '') or ''}
                                })
                    descendants.append({
                        "block_id": txt_id, "block_type": 2,
                        "text": {"elements": elements},
                        "children": [],
                    })
                descendants.append({
                    "block_id": cell_tid, "block_type": 32,
                    "table_cell": {}, "children": text_tids,
                })
            else:
                # Complex content: cell with empty placeholder, caller handles later
                placeholder_tid = f"{cell_tid}_p"
                descendants.append({
                    "block_id": cell_tid, "block_type": 32,
                    "table_cell": {}, "children": [placeholder_tid],
                })
                descendants.append({
                    "block_id": placeholder_tid, "block_type": 2,
                    "text": {"elements": [{"text_run": {"content": ""}}]},
                    "children": [],
                })
                complex_cell_indices.append(i)

        def _calc_column_widths(cell_contents_list, col_size):
            """Calculate proportional column widths based on content length.

            Each column gets width proportional to its max content length,
            scaled to fit a typical document content width (~800 units).
            """
            if not cell_contents_list or col_size <= 0:
                return []
            n_rows = len(cell_contents_list) // col_size
            if n_rows == 0:
                return [100] * col_size
            per_col_max = [0] * col_size
            for i, cell_block in enumerate(cell_contents_list):
                col_idx = i % col_size
                cell_content = cell_block.children if cell_block else []
                max_len = 0
                for b in cell_content:
                    if _is_text_block(b):
                        text_obj = getattr(b, 'text', None)
                        if text_obj and getattr(text_obj, 'elements', None):
                            for el in text_obj.elements:
                                tr = getattr(el, 'text_run', None)
                                if tr:
                                    max_len = max(max_len, len(getattr(tr, 'content', '') or ''))
                per_col_max[col_idx] = max(per_col_max[col_idx], max_len)
            raw = [min(max(l * 10, 60), 300) for l in per_col_max]
            total = sum(raw)
            if total <= 800:
                return raw
            return [max(int(w * 800 / total), 40) for w in raw]

        # Build table property
        table_prop = {"row_size": row_size, "column_size": column_size}
        if header_row:
            table_prop["header_row"] = True
        column_widths = _calc_column_widths(cell_contents_list, column_size)
        if column_widths:
            table_prop["column_width"] = column_widths

        table_descendant = {
            "block_id": tid,
            "block_type": 31,
            "table": {"property": table_prop},
            "children": cell_temp_ids,
        }

        body = {
            "children_id": [tid],
            "descendants": [table_descendant] + descendants,
        }

        if debug:
            print("[DEBUG] Descendant table request:")
            print(json.dumps(body, ensure_ascii=False, indent=2)[:2000])

        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(
                    f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}/descendant",
                    headers=headers,
                    json=body,
                    timeout=30,
                )
            except Exception as e:
                if attempt >= max_attempts:
                    raise
                sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)
                continue

            payload = resp.json()
            api_code = payload.get("code")
            if resp.status_code < 400 and api_code == 0:
                data = payload.get("data", {})
                children_data = data.get("children", [])
                if not children_data:
                    raise Exception("Descendant API returned no children data")
                # Reconstruct Block via SDK's dict-based init
                from lark_oapi.api.docx.v1.model.block import Block
                created_block = Block(d=children_data[0])
                return created_block, complex_cell_indices

            if (
                attempt < max_attempts
                and (resp.status_code in retryable_codes or api_code in retryable_api_codes)
            ):
                sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)
                continue

            raise Exception(
                f"Descendant table creation failed: http={resp.status_code}, "
                f"code={api_code}, msg={payload.get('msg')}"
            )

        raise Exception("Descendant table creation failed: max attempts reached")

    def _text_len(text_obj) -> int:
        if not text_obj or not getattr(text_obj, "elements", None):
            return 0
        total = 0
        for el in text_obj.elements:
            tr = getattr(el, "text_run", None)
            if tr and getattr(tr, "content", None):
                total += len(tr.content)
        return total

    def _block_summary(block) -> dict:
        # Keep it small: only what's useful for "invalid param" debugging.
        bt = getattr(block, "block_type", None)
        summary = {"block_type": bt}
        if bt == 2:  # TEXT
            summary["text_len"] = _text_len(getattr(block, "text", None))
        elif bt == 14:  # CODE
            summary["code_len"] = _text_len(getattr(block, "code", None))
        elif bt == 15:  # QUOTE
            summary["quote_len"] = _text_len(getattr(block, "quote", None))
        elif bt in (3, 4, 5, 6, 7, 8, 9, 10, 11):  # HEADINGS
            # heading1..heading9
            for lvl in range(1, 10):
                t = getattr(block, f"heading{lvl}", None)
                if t:
                    summary[f"heading{lvl}_len"] = _text_len(t)
                    break
        elif bt in (12, 13):  # LIST
            field = "bullet" if bt == 12 else "ordered"
            summary[f"{field}_len"] = _text_len(getattr(block, field, None))
            summary["children_count"] = len(getattr(block, "children", None) or [])
        elif bt == 31:  # TABLE
            summary["children_count"] = len(getattr(block, "children", None) or [])
        elif bt == 32:  # TABLE_CELL
            summary["children_count"] = len(getattr(block, "children", None) or [])
        elif bt == 27:  # IMAGE
            summary["has_image"] = bool(getattr(block, "image", None))
        else:
            summary["children_count"] = len(getattr(block, "children", None) or [])
        return summary
    
    # Helper to flush a batch of regular blocks
    MAX_BATCH_SIZE = 50  # Feishu API limits children to 50 per request

    def flush_batch(batch):
        if not batch:
            return []
        all_created = []
        for chunk_start in range(0, len(batch), MAX_BATCH_SIZE):
            chunk = batch[chunk_start:chunk_start + MAX_BATCH_SIZE]
            created = _flush_chunk(chunk, chunk_start)
            all_created.extend(created)
        return all_created

    def _flush_chunk(chunk, offset=0):
        """Send a single chunk (≤50 blocks) to the Feishu API."""
        request_body_builder = CreateDocumentBlockChildrenRequestBody.builder() \
            .children(chunk)
        if insert_index is not None:
            request_body_builder.index(insert_index + offset)
        request = CreateDocumentBlockChildrenRequest.builder() \
            .document_id(document_id) \
            .block_id(parent_id) \
            .request_body(request_body_builder.build()) \
            .build()
        if debug:
            request_payload = {
                "document_id": document_id,
                "block_id": parent_id,
                "request_body": _to_serializable(request.request_body),
            }
            print("[DEBUG] Feishu add_blocks request payload:")
            print(json.dumps(request_payload, ensure_ascii=False, indent=2))
        max_attempts = 5
        base_delay = 1.0
        retryable_codes = {429, 500, 502, 503, 504}

        for attempt in range(1, max_attempts + 1):
            try:
                response = client.docx.v1.document_block_children.create(request)
            except Exception as e:
                # Network-level/transient failures (e.g., ConnectionResetError 10054)
                if attempt >= max_attempts:
                    raise Exception(
                        f"Failed to add blocks after {max_attempts} attempts due to connection error: {e}"
                    ) from e
                sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)
                continue

            if response.success():
                return response.data.children

            # Retry only for common transient API errors
            if response.code in retryable_codes and attempt < max_attempts:
                sleep_seconds = (base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)
                continue

            debug_batch = [_block_summary(b) for b in chunk]
            raise Exception(
                f"Failed to add blocks: {response.code}, {response.msg}, {response.error}. "
                f"Batch summary: {json.dumps(debug_batch, ensure_ascii=False)}"
            )

        # Unreachable fallback for type checkers/readability.
        return []

    all_created_children = []
    current_batch = []
    
    for block in blocks:
        # 1. Save children content
        original_children = block.children
        table_requested_row_size = None
        column_size = None
        if (
            block.block_type == 31 and
            block.table and
            block.table.property and
            block.table.property.row_size
        ):
            table_requested_row_size = block.table.property.row_size
            column_size = getattr(block.table.property, 'column_size', None)
            # 不再限制为 9 行——API 可能已支持更多行数
            # 如果创建后 cell 数量不够，会触发 fallback 插入行
        
        # For TABLE blocks: try descendant API first (pre-populate content,
        # avoids creating empty cells + per-cell placeholder deletion).
        if block.block_type == 31:
            if current_batch:
                all_created_children.extend(flush_batch(current_batch))
                current_batch = []

            try:
                created_block, complex_cell_indices = _create_table_via_descendant(
                    document_id, parent_id or document_id, block,
                    original_children or [],
                    table_requested_row_size or 1,
                    column_size or 1,
                    debug,
                )
                all_created_children.append(created_block)

                # For complex cells (lists, images, etc.) that got an empty
                # placeholder, fall back to append-content + delete-placeholder.
                if complex_cell_indices and created_block.table and created_block.table.cells:
                    cell_ids = created_block.table.cells
                    cell_delete_jobs = []
                    for idx in complex_cell_indices:
                        if idx < len(cell_ids) and idx < len(original_children) and original_children[idx]:
                            cell_block = original_children[idx]
                            cell_content = cell_block.children if hasattr(cell_block, 'children') else None
                            if cell_content:
                                created_in_cell = add_blocks(
                                    document_id, cell_content,
                                    parent_id=cell_ids[idx], debug=debug,
                                )
                                if created_in_cell:
                                    cell_delete_jobs.append((cell_ids[idx], 1))
                    for cid, oc in cell_delete_jobs:
                        _batch_delete_block_children_range(
                            document_id, cid, start_index=0, end_index=oc,
                        )
                continue
            except Exception as e:
                if debug:
                    print(f"[DEBUG] Descendant table creation failed, falling back: {e}")
                # Fall through to flush_batch approach below

        # 2. Clear children for creation (create empty block first)
        block.children = None

        # 3. Create Block (flush_batch for non-TABLE blocks or TABLE fallback)
        if original_children or block.block_type == 31:
            if current_batch:
                all_created_children.extend(flush_batch(current_batch))
                current_batch = []

            created_blocks = flush_batch([block])
            all_created_children.extend(created_blocks)

            if not created_blocks:
                continue

            created_block = created_blocks[0]

            # 4. Handle Children
            if block.block_type == 31: # Table fallback (descendant failed)
                if not created_block.table or not created_block.table.cells:
                    print("Warning: Created table has no cells")
                    continue

                cell_ids = created_block.table.cells

                # Insert extra rows if API didn't create enough cells
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

                cell_delete_jobs = []
                _verified_placeholder = False
                for i, cell_id in enumerate(cell_ids):
                    if original_children and i < len(original_children):
                        cell_content = original_children[i].children
                        if cell_content:
                            old_count = 1
                            if debug and not _verified_placeholder:
                                actual_ids = _get_block_children_ids(document_id, cell_id)
                                actual_count = len(actual_ids)
                                if actual_count != old_count:
                                    print(
                                        f"[WARN] 单元格占位符数量异常: table={created_block.block_id}, "
                                        f"cell={cell_id}, expected={old_count}, actual={actual_count}"
                                    )
                                _verified_placeholder = True
                            created_in_cell = add_blocks(
                                document_id, cell_content,
                                parent_id=cell_id, debug=debug,
                            )
                            if old_count > 0 and len(created_in_cell or []) > 0:
                                cell_delete_jobs.append((cell_id, old_count))
                for cell_id, old_count in cell_delete_jobs:
                    _batch_delete_block_children_range(
                        document_id, cell_id, start_index=0, end_index=old_count,
                    )

            elif original_children: # General Nested Block (e.g. List)
                add_blocks(
                    document_id, original_children,
                    parent_id=created_block.block_id, debug=debug,
                )

        else:
            # No children, just add to batch
            current_batch.append(block)
            
    # Flush remaining
    if current_batch:
        all_created_children.extend(flush_batch(current_batch))
        
    return all_created_children

def set_public_permission(token: str):
    """
    Set document permission to 'Organization members can edit'.
    """
    client = get_client()
    
    # Construct request to update public permission
    # link_share_entity="tenant_editable" means organization members can edit
    request = PatchPermissionPublicRequest.builder() \
        .token(token) \
        .type("docx") \
        .request_body(PermissionPublic.builder()
            .external_access(True) \
            .security_entity("anyone_can_view") \
            .comment_entity("anyone_can_view") \
            .share_entity("anyone") \
            .link_share_entity("tenant_editable") \
            .build()) \
        .build()

    # Send request
    response = client.drive.v1.permission_public.patch(request)

    if not response.success():
        # Try with type="file" if "docx" fails, though docx should work for Docx
        request.type = "file"
        response = client.drive.v1.permission_public.patch(request)
        if not response.success():
             raise Exception(f"Failed to set permission: {response.code}, {response.msg}, {response.error}")
    
    return True


def delete_document(document_id: str, client=None) -> bool:
    """
    Delete a Docx document by token.
    Returns True on success.
    """
    if client is None:
        client = get_client()

    request = DeleteFileRequest.builder() \
        .file_token(document_id) \
        .type("docx") \
        .build()

    response = client.drive.v1.file.delete(request)

    if not response.success():
        raise Exception(
            f"Failed to delete document: {response.code}, {response.msg}, {response.error}"
        )

    return True


def delete_document(document_id: str, client=None) -> bool:
    """
    Delete a Docx document by token.
    Returns True on success.
    """
    if client is None:
        client = get_client()

    request = DeleteFileRequest.builder() \
        .file_token(document_id) \
        .type("docx") \
        .build()

    response = client.drive.v1.file.delete(request)

    if not response.success():
        raise Exception(
            f"Failed to delete document: {response.code}, {response.msg}, {response.error}"
        )

    return True
