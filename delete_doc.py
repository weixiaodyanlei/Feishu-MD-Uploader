import argparse
import sys
import lark_oapi as lark
from lark_oapi.api.drive.v1.model import *
from src.auth import get_client

def delete_document(token: str):
    """
    Delete a document (file) by its token.
    """
    client = get_client()

    # Construct request
    request = DeleteFileRequest.builder() \
        .file_token(token) \
        .type("docx") \
        .build()

    # Send request
    response = client.drive.v1.file.delete(request)

    if not response.success():
        print(f"❌ Failed to delete document: {response.code}, {response.msg}, {response.error}")
        return False

    print(f"✅ Successfully deleted document: {token}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Delete Feishu Document")
    parser.add_argument("token", help="The token of the document to delete")
    args = parser.parse_args()

    delete_document(args.token)

if __name__ == "__main__":
    main()
