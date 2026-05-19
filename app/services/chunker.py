from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from app.services.pdf_processor import PageText


@dataclass
class Chunk:
    chunk_id: str
    page: int
    text: str


def chunk_pages(pages: Iterable[PageText], max_chars: int = 1400, overlap: int = 180) -> List[Chunk]:
    chunks: List[Chunk] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        start = 0
        n = len(text)
        part = 1
        while start < n:
            end = min(start + max_chars, n)
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(chunk_id=f"p{page.page}_c{part}", page=page.page, text=piece))
            if end == n:
                break
            start = max(0, end - overlap)
            part += 1
    return chunks
