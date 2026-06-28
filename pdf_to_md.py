from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.pdf.extractor import PdfConversionError, extract_pdf
from src.pdf.markdown_writer import render_markdown, save_images
from src.pdf.typora_profile import classify_document


def convert_pdf_to_md(
    pdf_path: Path,
    output_path: Path | None = None,
    assets_dir: Path | None = None,
    *,
    no_overwrite: bool = False,
    clean_assets: bool = False,
    debug: bool = False,
) -> Path:
    if debug:
        logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    pdf_path = pdf_path.resolve()
    md_path = (output_path or pdf_path.with_suffix(".md")).resolve()
    assets_path = (assets_dir or md_path.parent / f"{md_path.stem}_assets").resolve()
    assets_dir_name = assets_path.name

    if no_overwrite and md_path.exists():
        raise PdfConversionError(f"Output already exists: {md_path}", exit_code=1)

    doc = extract_pdf(pdf_path)
    elements = classify_document(doc, debug=debug)

    for image in doc.images:
        filename = f"image_{image.image_index:03d}.{image.ext}"
        image.image_ref = f"{assets_dir_name}/{filename}"

    save_images(doc.images, assets_path, clean=clean_assets)
    markdown = render_markdown(elements, assets_dir_name)
    md_path.write_text(markdown, encoding="utf-8")

    page_count = max((b.page_index for b in doc.blocks), default=0) + 1
    logging.info("Pages processed: %s", page_count)
    logging.info("Images saved: %s", len(doc.images))
    logging.info("Output: %s", md_path)
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Typora-style text PDF to Markdown")
    parser.add_argument("pdf_file", help="Path to input PDF")
    parser.add_argument("-o", "--output", help="Output Markdown path")
    parser.add_argument("--assets-dir", help="Directory for extracted images")
    parser.add_argument("--no-overwrite", action="store_true", help="Refuse to overwrite existing output")
    parser.add_argument("--clean-assets", action="store_true", help="Delete assets dir before saving images")
    parser.add_argument("--debug", action="store_true", help="Verbose debug logging")
    args = parser.parse_args()

    try:
        convert_pdf_to_md(
            Path(args.pdf_file),
            Path(args.output) if args.output else None,
            Path(args.assets_dir) if args.assets_dir else None,
            no_overwrite=args.no_overwrite,
            clean_assets=args.clean_assets,
            debug=args.debug,
        )
    except PdfConversionError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(exc.exit_code)


if __name__ == "__main__":
    main()
