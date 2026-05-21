import fitz
import re
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    text: str
    page: int
    chunk_index: int


def extract_text_by_page(file_bytes: bytes) -> list[tuple[int, str]]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return [
        (i + 1, page.get_text().strip())
        for i, page in enumerate(doc)
        if page.get_text().strip()
    ]


def chunk_text(
    text: str,
    page: int,
    chunk_size: int = 600,
    overlap: int = 100
) -> list[DocumentChunk]:
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= chunk_size:
        return [DocumentChunk(text=text, page=page, chunk_index=0)]

    chunks = []
    start  = 0
    idx    = 0

    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            boundary = text.rfind('.', start, end)
            if boundary > start + (chunk_size // 2):
                end = boundary + 1

        chunk_str = text[start:end].strip()
        if chunk_str:
            chunks.append(DocumentChunk(
                text=chunk_str,
                page=page,
                chunk_index=idx
            ))
        idx   += 1
        start  = end - overlap

    return chunks


def parse_pdf_into_chunks(
    file_bytes: bytes,
    chunk_size: int = 600,
    overlap: int = 100
) -> list[DocumentChunk]:
    all_chunks = []
    for page_num, page_text in extract_text_by_page(file_bytes):
        all_chunks.extend(
            chunk_text(page_text, page=page_num,
                       chunk_size=chunk_size, overlap=overlap)
        )
    return all_chunks