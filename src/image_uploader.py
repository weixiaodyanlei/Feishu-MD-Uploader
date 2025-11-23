import os
import lark_oapi
from lark_oapi.api.drive.v1 import *
from lark_oapi.api.docx.v1 import *
from src.auth import get_client

class ImageUploader:
    def __init__(self, client: lark_oapi.Client):
        self.client = client
        self.cache = {}  # Cache for file_path -> token

    def upload_and_update_image(self, file_path: str, document_id: str, block_id: str) -> bool:
        """
        Upload an image to a specific Image Block and update the block.
        This follows the 3-step process:
        1. Image Block is already created (done by caller)
        2. Upload image with block_id as parent_node
        3. Update block with replace_image operation
        """
        if not os.path.exists(file_path):
            print(f"Warning: Image file not found: {file_path}")
            return False

        print(f"   Uploading: {os.path.basename(file_path)}")
        
        # Step 2: Upload image with block_id as parent_node
        # Important: use file object, not bytes
        file_size = os.path.getsize(file_path)
        file_obj = open(file_path, "rb")
        
        request = UploadAllMediaRequest.builder() \
            .request_body(UploadAllMediaRequestBody.builder()
                .file_name(os.path.basename(file_path))
                .parent_type("docx_image")
                .parent_node(block_id)
                .size(file_size)
                .file(file_obj)
                .build()) \
            .build()

        response = self.client.drive.v1.media.upload_all(request)
        file_obj.close()

        if not response.success():
            print(f"   Error: {response.code}, {response.msg}")
            return False

        file_token = response.data.file_token
        print(f"   Got file_token: {file_token[:20]}...")
        
        # Step 3: Update the Image Block with the file_token
        update_request = BatchUpdateDocumentBlockRequest.builder() \
            .document_id(document_id) \
            .request_body(BatchUpdateDocumentBlockRequestBody.builder()
                .requests([
                    UpdateBlockRequest.builder()
                        .block_id(block_id)
                        .replace_image(ReplaceImageRequest.builder()
                            .token(file_token)
                            .build())
                        .build()
                ])
                .build()) \
            .build()
        
        update_response = self.client.docx.v1.document_block.batch_update(update_request)
        
        if not update_response.success():
            print(f"   Error updating block: {update_response.code}, {update_response.msg}")
            return False
        
        return True
