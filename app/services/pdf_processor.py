from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF
from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


@dataclass
class PageText:
    page: int
    text: str
    extraction_method: str


def extract_pdf_text(path: str, ocr_if_needed: bool = True) -> List[PageText]:
    """Extract page-level text. Falls back to OCR for pages with little/no text."""
    doc = fitz.open(path)
    pages: List[PageText] = []

    for idx, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        method = "pymupdf_text"

        if ocr_if_needed and len(text) < 40:
            ocr_text = _ocr_page(page)
            if ocr_text.strip():
                text = ocr_text.strip()
                method = "tesseract_ocr"
            else:
                method = "empty_or_unreadable"

        pages.append(PageText(page=idx, text=clean_text(text), extraction_method=method))

    return pages


def _ocr_page(page: fitz.Page) -> str:
    if pytesseract is None:
        return ""
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\x00", " ").splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)
