from __future__ import annotations

from pathlib import Path

import fitz

from src.pdf.models import ExtractedDocument, ExtractedImage, LinkAnnotation, TextBlock


class PdfConversionError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def open_pdf_or_exit(pdf_path: Path) -> fitz.Document:
    if not pdf_path.exists():
        raise PdfConversionError(f"PDF not found: {pdf_path}", exit_code=1)
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise PdfConversionError(f"Cannot open PDF: {pdf_path} ({exc})", exit_code=1) from exc
    if doc.is_encrypted:
        raise PdfConversionError("Encrypted PDF is not supported", exit_code=1)
    return doc


def merge_spans_to_blocks(page_dict: dict, page_index: int) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(span.get("text", "") for span in spans).strip()
            if not text:
                continue
            first = spans[0]
            x0 = min(span["bbox"][0] for span in spans)
            y0 = min(span["bbox"][1] for span in spans)
            x1 = max(span["bbox"][2] for span in spans)
            y1 = max(span["bbox"][3] for span in spans)
            blocks.append(
                TextBlock(
                    text=text,
                    font=str(first.get("font", "")),
                    size=float(first.get("size", 0)),
                    flags=int(first.get("flags", 0)),
                    page_index=page_index,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                )
            )
    return blocks


def _extract_links(page: fitz.Page, page_index: int) -> list[LinkAnnotation]:
    links: list[LinkAnnotation] = []
    for link in page.get_links():
        uri = link.get("uri")
        rect = link.get("from")
        if not uri or rect is None:
            continue
        links.append(
            LinkAnnotation(
                uri=uri,
                page_index=page_index,
                x0=float(rect.x0),
                y0=float(rect.y0),
                x1=float(rect.x1),
                y1=float(rect.y1),
            )
        )
    return links


def _image_bbox(page: fitz.Page, xref: int) -> tuple[float, float, float, float]:
    for img in page.get_image_info(xrefs=True):
        if img.get("xref") == xref:
            bbox = img.get("bbox")
            if bbox:
                return (float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1))
    return (0.0, 0.0, 0.0, 0.0)


def extract_pdf(pdf_path: Path) -> ExtractedDocument:
    doc = open_pdf_or_exit(pdf_path)
    extracted = ExtractedDocument()
    seen_xrefs: set[int] = set()

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_dict = page.get_text("dict")
            extracted.blocks.extend(merge_spans_to_blocks(page_dict, page_index))
            extracted.links.extend(_extract_links(page, page_index))

            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    info = doc.extract_image(xref)
                except Exception:
                    continue
                x0, y0, x1, y1 = _image_bbox(page, xref)
                extracted.images.append(
                    ExtractedImage(
                        page_index=page_index,
                        x0=x0,
                        y0=y0,
                        xref=xref,
                        ext=str(info.get("ext", "png")),
                        data=info["image"],
                    )
                )
    finally:
        doc.close()

    if not any(b.text.strip() for b in extracted.blocks):
        raise PdfConversionError(
            "No extractable text found; this tool only supports text-based PDFs",
            exit_code=2,
        )

    extracted.blocks.sort(key=lambda b: (b.page_index, b.y0, b.x0))
    extracted.images.sort(key=lambda i: (i.page_index, i.y0, i.x0))
    for idx, image in enumerate(extracted.images, start=1):
        image.image_index = idx

    return extracted
