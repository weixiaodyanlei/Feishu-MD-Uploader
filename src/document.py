import json
import lark_oapi as lark
from lark_oapi.api.docx.v1.model import *
from lark_oapi.api.drive.v1.model import *
from .auth import get_client

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

def add_blocks(document_id: str, blocks: list, parent_id: str = None):
    """
    Add blocks to the document or a specific parent block.
    Handles Table blocks by creating them empty first and then populating cells.
    """
    if parent_id is None:
        parent_id = document_id
        
    client = get_client()
    
    # Helper to flush a batch of regular blocks
    def flush_batch(batch):
        if not batch:
            return []
        request = CreateDocumentBlockChildrenRequest.builder() \
            .document_id(document_id) \
            .block_id(parent_id) \
            .request_body(CreateDocumentBlockChildrenRequestBody.builder()
                .children(batch)
                .build()) \
            .build()
        response = client.docx.v1.document_block_children.create(request)
        if not response.success():
             raise Exception(f"Failed to add blocks: {response.code}, {response.msg}, {response.error}")
        return response.data.children

    all_created_children = []
    current_batch = []
    
    for block in blocks:
        if block.block_type == 31: # Table
            # Flush current batch first
            if current_batch:
                all_created_children.extend(flush_batch(current_batch))
                current_batch = []
            
            # Handle Table
            # 1. Save content (TableCell blocks)
            original_cells = block.children
            # 2. Clear children for creation (create empty table)
            block.children = None
            
            # 3. Create Table
            created_table_children = flush_batch([block])
            all_created_children.extend(created_table_children)
            
            if not created_table_children:
                continue
                
            created_table = created_table_children[0]
            
            # 4. Fill Cells
            if not created_table.table or not created_table.table.cells:
                print("Warning: Created table has no cells")
                continue
                
            cell_ids = created_table.table.cells
            
            # Check if dimensions match
            if len(cell_ids) != len(original_cells):
                print(f"Warning: Cell count mismatch. Created: {len(cell_ids)}, Parsed: {len(original_cells)}")
            
            # Recursively add content to cells
            for i, cell_id in enumerate(cell_ids):
                if i < len(original_cells):
                    # original_cells[i] is a TableCell block (32)
                    # We want its children (the content)
                    cell_content = original_cells[i].children
                    if cell_content:
                        # Recursive call to add content to the cell
                        add_blocks(document_id, cell_content, parent_id=cell_id)
                        
        else:
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
