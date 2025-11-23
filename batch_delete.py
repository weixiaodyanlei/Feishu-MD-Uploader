#!/usr/bin/env python3
"""
Batch delete Feishu documents created by the uploader.
This script lists all documents and allows selective or bulk deletion.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.auth import get_client
from src.config import Config
from lark_oapi.api.drive.v1.model import *
from lark_oapi.api.docx.v1.model import *

def list_documents(folder_token=None):
    """List all documents in the specified folder or root."""
    client = get_client()
    
    # Build request
    request = ListFileRequest.builder() \
        .page_size(100) \
        .folder_token(folder_token or "") \
        .build()
    
    response = client.drive.v1.file.list(request)
    
    if not response.success():
        print(f"❌ Failed to list documents: {response.code}, {response.msg}")
        return []
    
    documents = []
    if response.data and response.data.files:
        for file in response.data.files:
            if file.type == "docx":  # Only docx files
                documents.append({
                    'token': file.token,
                    'name': file.name,
                    'url': f"{Config.FEISHU_DOC_HOST}/docx/{file.token}"
                })
    
    return documents

def delete_document(token):
    """Delete a single document by token."""
    client = get_client()
    
    request = DeleteFileRequest.builder() \
        .file_token(token) \
        .type("docx") \
        .build()
    
    response = client.drive.v1.file.delete(request)
    
    return response.success()

def main():
    parser = argparse.ArgumentParser(
        description="Batch delete Feishu documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all documents
  python batch_delete.py --list
  
  # Delete specific documents by token
  python batch_delete.py token1 token2 token3
  
  # Delete all documents (with confirmation)
  python batch_delete.py --all
  
  # Delete all documents matching a pattern
  python batch_delete.py --pattern "Test"
        """
    )
    
    parser.add_argument("tokens", nargs="*", help="Document tokens to delete")
    parser.add_argument("--list", action="store_true", help="List all documents")
    parser.add_argument("--all", action="store_true", help="Delete all documents")
    parser.add_argument("--pattern", help="Delete documents matching this pattern in name")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    # List documents
    print("📋 Fetching documents...")
    docs = list_documents()
    
    if not docs:
        print("No documents found.")
        return
    
    # List mode
    if args.list:
        print(f"\n Found {len(docs)} documents:\n")
        for i, doc in enumerate(docs, 1):
            print(f"{i}. {doc['name']}")
            print(f"   Token: {doc['token']}")
            print(f"   URL: {doc['url']}\n")
        return
    
    # Determine which documents to delete
    to_delete = []
    
    if args.all:
        to_delete = docs
    elif args.pattern:
        pattern = args.pattern.lower()
        to_delete = [doc for doc in docs if pattern in doc['name'].lower()]
    elif args.tokens:
        token_set = set(args.tokens)
        to_delete = [doc for doc in docs if doc['token'] in token_set]
    else:
        parser.print_help()
        return
    
    if not to_delete:
        print("No documents match the criteria.")
        return
    
    # Show what will be deleted
    print(f"\n🗑️  Will delete {len(to_delete)} document(s):\n")
    for i, doc in enumerate(to_delete, 1):
        print(f"{i}. {doc['name']} ({doc['token']})")
    
    # Confirm
    if not args.yes:
        print("\n⚠️  This action cannot be undone!")
        confirm = input("Continue? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return
    
    # Delete
    print(f"\n🗑️  Deleting {len(to_delete)} document(s)...\n")
    success_count = 0
    fail_count = 0
    
    for doc in to_delete:
        print(f"Deleting: {doc['name']}...", end=" ")
        if delete_document(doc['token']):
            print("✅")
            success_count += 1
        else:
            print("❌")
            fail_count += 1
    
    print(f"\n✅ Successfully deleted: {success_count}")
    if fail_count > 0:
        print(f"❌ Failed to delete: {fail_count}")
    
    print("\n🎉 Cleanup complete!")

if __name__ == "__main__":
    main()
