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

    return response.data.document.document_id

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
    def flush_batch(batch):
        if not batch:
            return []
        request_body_builder = CreateDocumentBlockChildrenRequestBody.builder() \
            .children(batch)
        if insert_index is not None:
            request_body_builder.index(insert_index)
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

            debug_batch = [_block_summary(b) for b in batch]
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
        
        # 2. Clear children for creation (create empty block first)
        # Note: Feishu API doesn't support creating nested children directly in 'children' field for most blocks
        block.children = None
        
        # 3. Create Block
        # Flush current batch if we need to handle this block individually (e.g. Table or block with children)
        # Actually, if we strip children, we can batch create them?
        # Yes, but we need to map the created block back to its original children to populate them.
        # So we must create them one by one or maintain a mapping.
        # Simplest approach: Flush batch, create this block, populate children.
        
        if original_children or block.block_type == 31: # Has children or is Table
            # Flush current batch first
            if current_batch:
                all_created_children.extend(flush_batch(current_batch))
                current_batch = []
                
            # Create this block
            created_blocks = flush_batch([block])
            all_created_children.extend(created_blocks)
            
            if not created_blocks:
                continue
                
            created_block = created_blocks[0]
            
            # 4. Handle Children
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

                # Recursively add content to cells
                for i, cell_id in enumerate(cell_ids):
                    if original_children and i < len(original_children):
                        # original_children[i] is a TableCell block (32)
                        # We want its children (the content)
                        cell_content = original_children[i].children
                        if cell_content:
                            add_blocks(
                                document_id,
                                cell_content,
                                parent_id=cell_id,
                                insert_index=0,
                                debug=debug
                            )
            
            elif original_children: # General Nested Block (e.g. List)
                # Recursively add children to this block
                add_blocks(
                    document_id,
                    original_children,
                    parent_id=created_block.block_id,
                    debug=debug
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
