import argparse
import os
import sys
from pathlib import Path

# Add src to path so we can import modules if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.config import Config
from src.document import create_document, set_public_permission

def main():
    parser = argparse.ArgumentParser(description="Feishu Markdown Uploader")
    parser.add_argument("file", help="Path to the Markdown file")
    parser.add_argument("--title", help="Document title")
    parser.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    parser.add_argument("--env-file", help="Path to .env file")

    args = parser.parse_args()

    # Validate file exists
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        sys.exit(1)

    # Determine title
    title = args.title
    if not title:
        title = Path(args.file).stem

    print(f"🚀 Starting upload for '{title}'...")

    try:
        # 1. Create Document
        print("Creating document...")
        doc_token = create_document(title)
        print(f"✅ Document created. Token: {doc_token}")
        print(f"🔗 URL: {Config.FEISHU_DOC_HOST}/docx/{doc_token}")

        # 2. Set Permissions
        print("Setting permissions...")
        set_public_permission(doc_token)
        print("✅ Permissions set to 'Organization members can edit'.")

        print("\n🎉 Upload complete!")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
