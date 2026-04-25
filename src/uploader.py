from __future__ import annotations

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


def upload_one_markdown(
    md_path: Path,
    *,
    folder_token,
    source_type: int,
    title_override: str | None,
    client,
    debug: bool,
) -> str:
    """
    Create one Feishu doc from a Markdown file, upload blocks, images, set permission.
    Returns document token.
    """
    md_path = md_path.resolve()
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    title = title_override if title_override else md_path.stem
    markdown_dir = str(md_path.parent)

    print(f"🚀 Starting upload for '{title}' ({md_path.name})...")

    folder_token = folder_token or Config.FOLDER_TOKEN
    if debug:
        print("Creating document...")
        if folder_token:
            print(f"Using folder token: {folder_token}")
    doc_token = create_document(title, folder_token)
    if debug:
        print(f"✅ Document created. Token: {doc_token}")
    print(f"🔗 URL: {Config.FEISHU_DOC_HOST}/docx/{doc_token}")

    if debug:
        print("Parsing Markdown...")
    image_uploader = ImageUploader(client)
    md_parser = MarkdownParser(image_uploader, doc_token, source_type=source_type)
    blocks = md_parser.parse(content)
    if debug:
        print(f"✅ Parsed {len(blocks)} blocks.")

    if blocks:
        chunk_size = 50
        block_id_map = []
        total_chunks = (len(blocks) + chunk_size - 1) // chunk_size

        if TQDM_AVAILABLE and not debug:
            print("📤 Uploading content blocks...")
            pbar = tqdm(total=total_chunks, desc="Blocks", unit="chunk", ncols=80)
        else:
            pbar = None
            if debug:
                print("Uploading content blocks...")

        for i in range(0, len(blocks), chunk_size):
            chunk = blocks[i : i + chunk_size]
            response_children = add_blocks(doc_token, chunk, debug=debug)
            for child in response_children:
                block_id_map.append(child.block_id)

            if pbar:
                pbar.update(1)
            elif debug:
                print(f"   - Uploaded blocks {i+1} to {min(i+chunk_size, len(blocks))}")

        if pbar:
            pbar.close()
            print("✅ Content uploaded.")
        elif debug:
            print("✅ Content uploaded.")

        pending_images = md_parser.get_pending_images()
        if pending_images:
            if TQDM_AVAILABLE and not debug:
                print(f"🖼️  Uploading {len(pending_images)} images...")
                img_pbar = tqdm(total=len(pending_images), desc="Images", unit="img", ncols=80)
            else:
                img_pbar = None
                if debug:
                    print(f"Uploading {len(pending_images)} images...")

            for img_info in pending_images:
                block_index = img_info["block_index"]
                image_path = img_info["image_path"]
                temp_file_path = None

                if image_path.startswith(("http://", "https://")):
                    if debug:
                        print(f"   - Downloading image: {image_path}")
                    try:
                        response = requests.get(image_path, stream=True, timeout=10)
                        response.raise_for_status()

                        suffix = os.path.splitext(image_path)[1]
                        if not suffix or len(suffix) > 5 or "?" in suffix:
                            suffix = ".png"

                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            for chunk in response.iter_content(chunk_size=8192):
                                tmp.write(chunk)
                            temp_file_path = tmp.name
                            image_path = temp_file_path

                    except Exception as e:
                        if debug:
                            print(f"     ❌ Failed to download image: {e}")
                        if img_pbar:
                            img_pbar.update(1)
                        continue
                else:
                    if not os.path.isabs(image_path):
                        image_path = os.path.join(markdown_dir, image_path)

                if block_index < len(block_id_map):
                    block_id = block_id_map[block_index]
                    if debug:
                        print(f"   - Uploading image: {os.path.basename(image_path)} to block")
                    success = image_uploader.upload_and_update_image(
                        image_path, doc_token, block_id
                    )
                    if debug:
                        if success:
                            print("     ✅ Image uploaded and set")
                        else:
                            print("     ❌ Failed to upload image")

                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

                if img_pbar:
                    img_pbar.update(1)

            if img_pbar:
                img_pbar.close()
                print("✅ Images processed.")
            elif debug:
                print("✅ Images processed.")

    if debug:
        print("Setting permissions...")
    set_public_permission(doc_token)
    if debug:
        print("✅ Permissions set to 'Organization members can edit'.")

    print(f"🎉 Upload complete: {md_path.name}\n")
    return doc_token


def main():
    parser = argparse.ArgumentParser(description="Feishu Markdown Uploader")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Path to a single Markdown file (omit when using --dir)",
    )
    parser.add_argument(
        "--dir",
        dest="upload_dir",
        metavar="PATH",
        help="Upload every *.md in this directory (non-recursive). Mutually exclusive with FILE.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="With --dir, also include Markdown files in subdirectories (**/*.md).",
    )
    parser.add_argument("--title", help="Document title (single-file mode only; default: file stem)")
    parser.add_argument("--folder-token", help="Target Feishu folder token")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (show all logs)")
    parser.add_argument("--env-file", help="Path to .env file")
    parser.add_argument(
        "--type",
        type=int,
        choices=[1, 2, 3],
        default=1,
        metavar="N",
        help=(
            "Markdown 来源类型（专属预处理）: "
            "1=腾讯云开发者, 2=腾讯技术工程, 3=阿里云开发者 (默认: 1)"
        ),
    )

    args = parser.parse_args()

    setup_logging(args.debug)

    if args.upload_dir and args.file:
        print("Error: specify either FILE or --dir, not both.")
        sys.exit(1)
    if not args.upload_dir and not args.file:
        print("Error: provide a Markdown FILE or --dir PATH.")
        sys.exit(1)

    client = get_client(debug=args.debug)
    folder_token = args.folder_token or Config.FOLDER_TOKEN

    try:
        if args.file:
            if not os.path.isfile(args.file):
                print(f"Error: File '{args.file}' not found.")
                sys.exit(1)
            upload_one_markdown(
                Path(args.file),
                folder_token=folder_token,
                source_type=args.type,
                title_override=args.title,
                client=client,
                debug=args.debug,
            )
            return

        # Directory mode
        dir_path = Path(args.upload_dir).expanduser().resolve()
        if not dir_path.is_dir():
            print(f"Error: Not a directory: {dir_path}")
            sys.exit(1)

        if args.recursive:
            md_files = sorted(dir_path.rglob("*.md"))
        else:
            md_files = sorted(dir_path.glob("*.md"))

        if not md_files:
            print(f"No .md files found under: {dir_path}")
            sys.exit(1)

        if args.title and args.debug:
            print("[DEBUG] --title is ignored in --dir mode (each doc uses the .md file stem).")

        failed = []
        for idx, md in enumerate(md_files, start=1):
            print(f"[{idx}/{len(md_files)}] {md}")
            try:
                upload_one_markdown(
                    md,
                    folder_token=folder_token,
                    source_type=args.type,
                    title_override=None,
                    client=client,
                    debug=args.debug,
                )
            except Exception as e:
                print(f"❌ Failed: {md} — {e}")
                if args.debug:
                    import traceback
                    traceback.print_exc()
                failed.append(str(md))

        if failed:
            print(f"\nFinished with {len(failed)} failure(s) out of {len(md_files)} file(s).")
            sys.exit(1)
        print(f"All {len(md_files)} file(s) uploaded successfully.")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
