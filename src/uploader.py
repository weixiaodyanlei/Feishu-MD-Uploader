import argparse
import os
import sys
from pathlib import Path

# Add src to path so we can import modules if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.config import Config
from src.document import create_document, set_public_permission, add_blocks
from src.markdown_parser import MarkdownParser
from src.image_uploader import ImageUploader
from src.auth import get_client

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

    # Read file content
    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    # Determine title
    title = args.title
    if not title:
        title = Path(args.file).stem

    print(f"🚀 Starting upload for '{title}'...")
    
    client = get_client() # Initialize client for ImageUploader

    try:
        # 1. Create Document (First, to get document_id for image upload)
        print("Creating document...")
        doc_token = create_document(title)
        print(f"✅ Document created. Token: {doc_token}")
        print(f"🔗 URL: {Config.FEISHU_DOC_HOST}/docx/{doc_token}")

        # 2. Parse Markdown (with ImageUploader)
        print("Parsing Markdown...")
        image_uploader = ImageUploader(client)
        md_parser = MarkdownParser(image_uploader, doc_token)
        blocks = md_parser.parse(content)
        print(f"✅ Parsed {len(blocks)} blocks.")

        # 3. Add Content
        if blocks:
            print("Uploading content blocks...")
            chunk_size = 50
            block_id_map = []  # Map block index to block_id
            
            for i in range(0, len(blocks), chunk_size):
                chunk = blocks[i:i + chunk_size]
                response_children = add_blocks(doc_token, chunk)
                # Store block_ids for later image upload
                for child in response_children:
                    block_id_map.append(child.block_id)
                print(f"   - Uploaded blocks {i+1} to {min(i+chunk_size, len(blocks))}")
            print("✅ Content uploaded.")
            
            # 4. Upload and update images
            pending_images = md_parser.get_pending_images()
            if pending_images:
                print(f"Uploading {len(pending_images)} images...")
                # Get base directory of Markdown file
                markdown_dir = os.path.dirname(os.path.abspath(args.file))
                
                for img_info in pending_images:
                    block_index = img_info['block_index']
                    image_path = img_info['image_path']
                    # Resolve relative path to absolute
                    if not os.path.isabs(image_path):
                        image_path = os.path.join(markdown_dir, image_path)
                    
                    if block_index < len(block_id_map):
                        block_id = block_id_map[block_index]
                        print(f"   - Uploading image: {os.path.basename(image_path)} to block")
                        success = image_uploader.upload_and_update_image(image_path, doc_token, block_id)
                        if success:
                            print(f"     ✅ Image uploaded and set")
                        else:
                            print(f"     ❌ Failed to upload image")
                print("✅ Images processed.")

        # 5. Set Permissions
        print("Setting permissions...")
        set_public_permission(doc_token)
        print("✅ Permissions set to 'Organization members can edit'.")

        print("\n🎉 Upload complete!")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
