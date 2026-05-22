import re
import time
import fitz
from dataclasses import dataclass
from app.core.config import settings


@dataclass
class DocumentChunk:
    text: str
    page: int
    chunk_index: int


SUPPORTED_IMAGE_TYPES = {
    "image/jpeg":   "jpeg",
    "image/jpg":    "jpeg",
    "image/png":    "png",
    "image/webp":   "webp",
    "image/gif":    "gif",
    "image/bmp":    "bmp",
}

SUPPORTED_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"
}


# ── Native Text Extraction ────────────────────────────────────────────────────

def extract_text_by_page(file_bytes: bytes) -> list[tuple[int, str]]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return [
        (i + 1, page.get_text().strip())
        for i, page in enumerate(doc)
        if page.get_text().strip()
    ]


def is_scanned_pdf(file_bytes: bytes, min_text_chars: int = 100) -> bool:
    doc        = fitz.open(stream=file_bytes, filetype="pdf")
    total_text = ""
    for page in doc:
        total_text += page.get_text().strip()
    return len(total_text) < min_text_chars


# ── Chunking ──────────────────────────────────────────────────────────────────

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


# ── Smart Truncation ──────────────────────────────────────────────────────────

def smart_truncate(
    text: str,
    total_pages: int,
    max_chars: int = 12000
) -> tuple[str, str]:
    total_chars = len(text)

    if total_chars <= max_chars:
        return text, ""

    if total_chars <= max_chars * 2:
        first     = int(max_chars * 0.60)
        last      = max_chars - first
        truncated = (
            text[:first]
            + "\n\n[... middle section not analyzed ...]\n\n"
            + text[-last:]
        )
        note = (
            f"Document has {total_chars:,} chars (~{total_pages} pages). "
            f"Analyzed first and last sections."
        )
        return truncated, note

    first_end   = int(max_chars * 0.40)
    middle_size = int(max_chars * 0.35)
    last_size   = int(max_chars * 0.25)
    mid_start   = (total_chars // 2) - (middle_size // 2)
    mid_end     = mid_start + middle_size

    truncated = (
        text[:first_end]
        + "\n\n[... section 1 ends — section 2 begins ...]\n\n"
        + text[mid_start:mid_end]
        + "\n\n[... section 2 ends — final section begins ...]\n\n"
        + text[-last_size:]
    )
    note = (
        f"Large document: {total_chars:,} chars across ~{total_pages} pages. "
        f"Analyzed beginning (40%), middle sample (35%), and end (25%)."
    )
    return truncated, note


# ── Gemini OCR — PDF ──────────────────────────────────────────────────────────

async def ocr_with_gemini_inline(file_bytes: bytes) -> str:
    """Send PDF bytes directly to Gemini. Best for files under 20MB."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    print("[OCR] Gemini inline PDF processing...")

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="application/pdf",
                            data=file_bytes
                        )
                    ),
                    types.Part(text=_ocr_instruction())
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192,
        )
    )

    extracted = response.text.strip()
    print(f"[OCR] Inline PDF complete: {len(extracted):,} chars")
    return extracted


async def ocr_with_gemini_files_api(
    file_bytes: bytes,
    filename: str
) -> str:
    """Upload PDF via Gemini Files API. Best for files over 20MB."""
    from google import genai
    from google.genai import types
    import io

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    size_mb = len(file_bytes) / (1024 * 1024)
    print(f"[OCR] Uploading to Gemini Files API: {size_mb:.1f} MB...")

    file_obj = client.files.upload(
        file=io.BytesIO(file_bytes),
        config={
            "mime_type":    "application/pdf",
            "display_name": filename
        }
    )

    print(f"[OCR] Uploaded: {file_obj.name} | State: {file_obj.state.name}")

    # Wait for processing
    max_wait = 60
    waited   = 0
    while file_obj.state.name == "PROCESSING" and waited < max_wait:
        print(f"[OCR] Processing... ({waited}s)")
        time.sleep(3)
        waited   += 3
        file_obj  = client.files.get(name=file_obj.name)

    if file_obj.state.name != "ACTIVE":
        raise ValueError(
            f"Gemini file processing failed. State: {file_obj.state.name}"
        )

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        file_data=types.FileData(
                            mime_type="application/pdf",
                            file_uri=file_obj.uri
                        )
                    ),
                    types.Part(text=_ocr_instruction())
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192,
        )
    )

    extracted = response.text.strip()
    print(f"[OCR] Files API complete: {len(extracted):,} chars")

    # Delete uploaded file
    try:
        client.files.delete(name=file_obj.name)
        print(f"[OCR] Uploaded file deleted")
    except Exception as e:
        print(f"[OCR] Warning: could not delete file: {e}")

    return extracted


# ── Gemini OCR — Image ────────────────────────────────────────────────────────

async def ocr_image_with_gemini(
    file_bytes: bytes,
    mime_type: str
) -> str:
    """
    Extract text from image using Gemini vision.
    Supports: JPG, PNG, WEBP, GIF, BMP
    Works for screenshots, photos of contracts, scanned pages.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # Normalize mime type
    if mime_type == "image/jpg":
        mime_type = "image/jpeg"
    if mime_type == "image/bmp":
        mime_type = "image/png"  # Gemini handles BMP as PNG

    print(f"[OCR] Gemini image OCR: {mime_type} | {len(file_bytes):,} bytes")

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=file_bytes
                        )
                    ),
                    types.Part(text=_ocr_instruction())
                ]
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192,
        )
    )

    extracted = response.text.strip()
    print(f"[OCR] Image OCR complete: {len(extracted):,} chars")
    return extracted


async def ocr_multi_image_with_gemini(
    images: list[tuple[bytes, str]]   # list of (file_bytes, mime_type)
) -> str:
    """
    Extract text from multiple images in one Gemini call.
    Used when a contract is split across multiple image files.
    Max 16 images per call.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    print(f"[OCR] Multi-image OCR: {len(images)} images")

    parts = []
    for i, (img_bytes, mime_type) in enumerate(images):
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        parts.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type=mime_type,
                    data=img_bytes
                )
            )
        )

    parts.append(types.Part(text=_ocr_instruction()))

    response = client.models.generate_content(
        model=settings.GEMINI_LLM_MODEL,
        contents=[types.Content(role="user", parts=parts)],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=8192,
        )
    )

    extracted = response.text.strip()
    print(f"[OCR] Multi-image complete: {len(extracted):,} chars")
    return extracted


# ── OCR Instruction ───────────────────────────────────────────────────────────

def _ocr_instruction() -> str:
    return (
        "Extract ALL text from this document exactly as written. "
        "CRITICAL RULES:\n"
        "- Preserve the ORIGINAL language — do NOT translate\n"
        "- If Amharic (አማርኛ), extract in Amharic\n"
        "- If Oromiffa (Afaan Oromoo), extract in Oromiffa\n"
        "- If English, extract in English\n"
        "- Preserve headings, numbered lists, and paragraph structure\n"
        "- Include ALL text visible in the document\n"
        "- Do not add commentary, summaries, or explanations\n"
        "- Return ONLY the extracted text"
    )


# ── Main Extraction Pipeline ──────────────────────────────────────────────────

def get_mime_type_from_filename(filename: str) -> str:
    """Detect mime type from file extension."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        ".pdf":  "application/pdf",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
        ".gif":  "image/gif",
        ".bmp":  "image/bmp",
    }
    return mime_map.get(ext, "application/octet-stream")


async def extract_text_with_ocr_fallback(
    file_bytes: bytes,
    filename: str = "document.pdf"
) -> tuple[str, int, bool]:
    """
    Universal text extraction pipeline.

    Handles:
    - Normal PDF       → pymupdf native (fast, free)
    - Scanned PDF      → Gemini OCR
    - Screenshot (PNG/JPG/WEBP) → Gemini vision OCR
    - Photo of contract → Gemini vision OCR

    Returns: (extracted_text, total_pages, ocr_was_used)
    """
    ext      = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    size_mb  = len(file_bytes) / (1024 * 1024)
    is_image = ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

    # ── Image file (screenshot / photo) ──────────────────────────────────────
    if is_image:
        print(f"[EXTRACT] Image file detected: {ext} | {size_mb:.1f} MB")

        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "Image files require OCR. "
                "Please add GEMINI_API_KEY to your .env file."
            )

        mime_type = get_mime_type_from_filename(filename)
        ocr_text  = await ocr_image_with_gemini(file_bytes, mime_type)

        if not ocr_text or len(ocr_text.strip()) < 10:
            raise ValueError(
                "Could not extract text from image. "
                "Make sure the image is clear and contains readable text."
            )

        print(f"[EXTRACT] Image OCR complete: {len(ocr_text):,} chars")
        return ocr_text, 1, True

    # ── PDF file ──────────────────────────────────────────────────────────────
    doc         = fitz.open(stream=file_bytes, filetype="pdf")
    total_pages = len(doc)

    # Try native text extraction
    pages_text = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            pages_text.append(text)

    full_text = "\n\n".join(pages_text)

    # Native extraction succeeded
    if len(full_text.strip()) >= 100:
        print(
            f"[EXTRACT] Native PDF: "
            f"{len(full_text):,} chars | {total_pages} pages"
        )
        return full_text, total_pages, False

    # Scanned PDF
    print(
        f"[EXTRACT] Scanned PDF: only {len(full_text)} chars "
        f"from {total_pages} pages — switching to Gemini OCR..."
    )

    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "This PDF is scanned and requires OCR. "
            "Please add GEMINI_API_KEY to your .env file. "
            "OCR always uses Gemini regardless of LLM_PROVIDER."
        )

    if size_mb < 20:
        print(f"[EXTRACT] Using inline API ({size_mb:.1f} MB)")
        ocr_text = await ocr_with_gemini_inline(file_bytes)
    else:
        print(f"[EXTRACT] Using Files API ({size_mb:.1f} MB)")
        ocr_text = await ocr_with_gemini_files_api(file_bytes, filename)

    if not ocr_text or len(ocr_text.strip()) < 50:
        raise ValueError(
            "OCR extraction returned insufficient text. "
            "The document may be blurry, corrupted, or unsupported."
        )

    return ocr_text, total_pages, True