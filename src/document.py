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
        # 1. Save children content
        original_children = block.children
        
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
                # Recursively add content to cells
                for i, cell_id in enumerate(cell_ids):
                    if original_children and i < len(original_children):
                        # original_children[i] is a TableCell block (32)
                        # We want its children (the content)
                        cell_content = original_children[i].children
                        if cell_content:
                            add_blocks(document_id, cell_content, parent_id=cell_id)
            
            elif original_children: # General Nested Block (e.g. List)
                # Recursively add children to this block
                add_blocks(document_id, original_children, parent_id=created_block.block_id)
                
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
