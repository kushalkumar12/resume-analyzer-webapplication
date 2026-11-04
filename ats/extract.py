"""Document extraction module for PDF and DOCX files."""

import io
import re
from typing import Tuple, Dict, Any, Optional
import pypdf
import docx
from ats.security import sanitize_input_text


class ExtractionResult:
    def __init__(self, text: str, page_count: int, word_count: int, is_scanned_or_empty: bool, warning: str = ""):
        self.text = text
        self.page_count = page_count
        self.word_count = word_count
        self.is_scanned_or_empty = is_scanned_or_empty
        self.warning = warning


def normalize_document_text(raw_text: str) -> str:
    """Normalizes whitespace, line breaks, and tabs while preserving paragraph structure."""
    if not raw_text:
        return ""

    sanitized = sanitize_input_text(raw_text)

    # Replace multiple spaces/tabs with single space within lines
    lines = []
    for line in sanitized.split("\n"):
        clean_line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(clean_line)

    # Collapse more than 2 consecutive blank lines into 2 blank lines
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return collapsed.strip()


def extract_text_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Extracts text from PDF bytes safely.

    Fixes bug where page.extract_text() returning None turns into the string 'None'.
    Detects scanned or image-based PDFs when extracted text is suspiciously short.
    """
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    extracted_pages = []

    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        extracted_pages.append(page_text.strip())

    combined_text = "\n\n".join(extracted_pages)
    normalized = normalize_document_text(combined_text)

    words = normalized.split()
    word_count = len(words)

    is_scanned_or_empty = False
    warning = ""

    if word_count < 30:
        is_scanned_or_empty = True
        warning = (
            "Extracted text is empty or very short (< 30 words). "
            "This document appears to be a scanned image or non-OCR PDF. "
            "ATS software requires selectable, machine-readable text."
        )

    return ExtractionResult(
        text=normalized,
        page_count=page_count,
        word_count=word_count,
        is_scanned_or_empty=is_scanned_or_empty,
        warning=warning
    )


def extract_text_from_docx(docx_bytes: bytes) -> ExtractionResult:
    """Extracts text from DOCX bytes including paragraphs and table contents."""
    doc = docx.Document(io.BytesIO(docx_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    # Also capture table contents
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)

    combined = "\n\n".join(paragraphs)
    normalized = normalize_document_text(combined)

    words = normalized.split()
    word_count = len(words)

    is_scanned_or_empty = word_count < 20
    warning = "Document text is empty or unusually short." if is_scanned_or_empty else ""

    # Estimate page count for DOCX based on ~400 words per standard resume page
    estimated_pages = max(1, (word_count + 399) // 400)

    return ExtractionResult(
        text=normalized,
        page_count=estimated_pages,
        word_count=word_count,
        is_scanned_or_empty=is_scanned_or_empty,
        warning=warning
    )


def extract_document(file_name: str, file_bytes: bytes) -> ExtractionResult:
    """Dispatches extraction according to file extension."""
    ext = file_name.lower().split(".")[-1]
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == "docx":
        return extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type .{ext}")
