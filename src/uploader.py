import argparse
import os
import sys
from pathlib import Path
import requests
import tempfile
import logging

# Add src to path so we can import modules if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.config import Config
from src.document import create_document, set_public_permission, add_blocks
from src.markdown_parser import MarkdownParser
from src.image_uploader import ImageUploader
from src.auth import get_client

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None

def setup_logging(debug=False):
    """Setup logging configuration"""
    if debug:
        # Debug mode: show all logs
        logging.basicConfig(
            level=logging.DEBUG,
            format='[%(levelname)s] %(message)s'
        )
    else:
        # Normal mode: only show warnings and errors
        logging.basicConfig(
            level=logging.WARNING,
            format='%(message)s'
        )
        # Disable Lark SDK debug logs
        logging.getLogger('lark_oapi').setLevel(logging.WARNING)

def main():
    parser = argparse.ArgumentParser(description="Feishu Markdown Uploader")
    parser.add_argument("file", help="Path to the Markdown file")
    parser.add_argument("--title", help="Document title")
    parser.add_argument("--folder-token", help="Target Feishu folder token")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (show all logs)")
    parser.add_argument("--env-file", help="Path to .env file")

    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.debug)

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
    
    client = get_client(debug=args.debug) # Initialize client for ImageUploader

    try:
        folder_token = args.folder_token or Config.FOLDER_TOKEN
        # 1. Create Document (First, to get document_id for image upload)
        if args.debug:
            print("Creating document...")
            if folder_token:
                print(f"Using folder token: {folder_token}")
        doc_token = create_document(title, folder_token)
        if args.debug:
            print(f"✅ Document created. Token: {doc_token}")
        print(f"🔗 URL: {Config.FEISHU_DOC_HOST}/docx/{doc_token}")

        # 2. Parse Markdown (with ImageUploader)
        if args.debug:
            print("Parsing Markdown...")
        image_uploader = ImageUploader(client)
        md_parser = MarkdownParser(image_uploader, doc_token)
        blocks = md_parser.parse(content)
        if args.debug:
            print(f"✅ Parsed {len(blocks)} blocks.")

        # 3. Add Content
        if blocks:
            chunk_size = 50
            block_id_map = []  # Map block index to block_id
            total_chunks = (len(blocks) + chunk_size - 1) // chunk_size
            
            # Use tqdm for progress bar if available and not in debug mode
            if TQDM_AVAILABLE and not args.debug:
                print("📤 Uploading content blocks...")
                pbar = tqdm(total=total_chunks, desc="Blocks", unit="chunk", ncols=80)
            else:
                pbar = None
                if args.debug:
                    print("Uploading content blocks...")
            
            for i in range(0, len(blocks), chunk_size):
                chunk = blocks[i:i + chunk_size]
                response_children = add_blocks(doc_token, chunk, debug=args.debug)
                # Store block_ids for later image upload
                for child in response_children:
                    block_id_map.append(child.block_id)
                
                if pbar:
                    pbar.update(1)
                elif args.debug:
                    print(f"   - Uploaded blocks {i+1} to {min(i+chunk_size, len(blocks))}")
            
            if pbar:
                pbar.close()
                print("✅ Content uploaded.")
            elif args.debug:
                print("✅ Content uploaded.")
            
            # 4. Upload and update images
            pending_images = md_parser.get_pending_images()
            if pending_images:
                # Get base directory of Markdown file
                markdown_dir = os.path.dirname(os.path.abspath(args.file))
                
                # Use tqdm for progress bar if available and not in debug mode
                if TQDM_AVAILABLE and not args.debug:
                    print(f"🖼️  Uploading {len(pending_images)} images...")
                    img_pbar = tqdm(total=len(pending_images), desc="Images", unit="img", ncols=80)
                else:
                    img_pbar = None
                    if args.debug:
                        print(f"Uploading {len(pending_images)} images...")

                for img_info in pending_images:
                    block_index = img_info['block_index']
                    image_path = img_info['image_path']
                    temp_file_path = None

                    # Check if it's a URL
                    if image_path.startswith(('http://', 'https://')):
                        if args.debug:
                            print(f"   - Downloading image: {image_path}")
                        try:
                            response = requests.get(image_path, stream=True, timeout=10)
                            response.raise_for_status()
                            
                            # Determine extension
                            suffix = os.path.splitext(image_path)[1]
                            # Basic validation for extension
                            if not suffix or len(suffix) > 5 or '?' in suffix:
                                suffix = '.png'
                                
                            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                for chunk in response.iter_content(chunk_size=8192):
                                    tmp.write(chunk)
                                temp_file_path = tmp.name
                                image_path = temp_file_path # Update path to local temp file
                                
                        except Exception as e:
                            if args.debug:
                                print(f"     ❌ Failed to download image: {e}")
                            if img_pbar:
                                img_pbar.update(1)
                            continue
                    else:
                        # Resolve relative path to absolute
                        if not os.path.isabs(image_path):
                            image_path = os.path.join(markdown_dir, image_path)
                    
                    if block_index < len(block_id_map):
                        block_id = block_id_map[block_index]
                        if args.debug:
                            print(f"   - Uploading image: {os.path.basename(image_path)} to block")
                        success = image_uploader.upload_and_update_image(image_path, doc_token, block_id)
                        if args.debug:
                            if success:
                                print(f"     ✅ Image uploaded and set")
                            else:
                                print(f"     ❌ Failed to upload image")
                            
                    # Clean up temp file
                    if temp_file_path and os.path.exists(temp_file_path):
                        os.remove(temp_file_path)
                    
                    if img_pbar:
                        img_pbar.update(1)
                
                if img_pbar:
                    img_pbar.close()
                    print("✅ Images processed.")
                elif args.debug:
                    print("✅ Images processed.")

        # 5. Set Permissions
        if args.debug:
            print("Setting permissions...")
        set_public_permission(doc_token)
        if args.debug:
            print("✅ Permissions set to 'Organization members can edit'.")

        print("\n🎉 Upload complete!")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
