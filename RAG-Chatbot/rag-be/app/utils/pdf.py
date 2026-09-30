"""PDF utilities: everything a RAG project needs to do with PDFs, in one place.

CHECKLIST when building the next RAG (what to decide / do for PDFs)
  1. VALIDATE uploads ............ `validate(data)`        magic bytes, size, page limit, encryption
  2. EXTRACT text per page ....... `extract_pages(path)`   keeps page numbers -> citations "file.pdf p.7"
  3. CLEAN the text .............. `clean_pages(pages)`    drops repeated headers/footers, page numbers,
                                                           fixes "hyphen-\\nated" words (hurts retrieval otherwise)
  4. DETECT scanned PDFs ......... `looks_scanned(path)`   no text layer => needs OCR (see below)
  5. READ metadata ............... `read_info(path)`       pages, title, author, encrypted...
  6. MANAGE files ................ `split`, `extract_range`, `merge`   e.g. split a 900-page manual, merge exports
  7. FRONTEND mirror ............. rag-ui/utils/files/pdf.ts   (pre-upload checks, open at page N)

OCR (not built in, on purpose): scanned PDFs have images, not text. Options: `ocrmypdf file.pdf out.pdf`
(adds a text layer, then this module just works), or render pages with pdf2image + pytesseract, or send pages to
a vision model (Gemini/GPT-4o accept PDFs/images). `looks_scanned` tells you when you need one of these.

Library: pypdf (pure Python, no system deps). For layout-heavy PDFs (tables, columns) consider `pdfplumber` or
PyMuPDF - swap only `extract_pages`, the rest of the module stays the same.
"""
from __future__ import annotations

import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Union

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

MAGIC = b"%PDF-"
Pages = list[tuple[int, str]]  # [(page_number starting at 1, text)]
Source = Union[str, Path, bytes]


class PdfError(ValueError):
    """A PDF problem that is safe to show to the user."""


@dataclass
class PdfInfo:
    pages: int
    encrypted: bool
    title: str = ""
    author: str = ""
    subject: str = ""
    producer: str = ""
    created: str = ""
    size_bytes: int = 0
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- open / validate
def is_pdf(data: bytes) -> bool:
    """PDFs start with '%PDF-' (some producers put junk in the first 1 KB)."""
    return MAGIC in data[:1024]


def _open(src: Source, password: str | None = None) -> PdfReader:
    stream = io.BytesIO(src) if isinstance(src, bytes) else str(src)
    try:
        reader = PdfReader(stream)
    except (PdfReadError, OSError, ValueError) as e:
        raise PdfError(f"Not a readable PDF: {e}") from e
    if reader.is_encrypted:
        # empty user password is common ("owner-locked" PDFs still open)
        if not reader.decrypt(password or ""):
            raise PdfError("PDF is password protected - provide the password or remove protection")
    return reader


def validate(src: Source, *, max_pages: int = 2000, password: str | None = None) -> PdfInfo:
    """Raise PdfError unless this is a readable, not-too-big PDF. Returns its info."""
    data = src if isinstance(src, bytes) else Path(src).read_bytes()[:1024]
    if not is_pdf(data):
        raise PdfError("File does not look like a PDF (missing %PDF header)")
    info = read_info(src, password)
    if info.pages == 0:
        raise PdfError("PDF has no pages")
    if info.pages > max_pages:
        raise PdfError(f"PDF has {info.pages} pages; the limit is {max_pages} (use split() first)")
    return info


def read_info(src: Source, password: str | None = None) -> PdfInfo:
    size = len(src) if isinstance(src, bytes) else Path(src).stat().st_size
    stream = io.BytesIO(src) if isinstance(src, bytes) else str(src)
    try:
        raw = PdfReader(stream)
    except (PdfReadError, OSError, ValueError) as e:
        raise PdfError(f"Not a readable PDF: {e}") from e
    encrypted = raw.is_encrypted
    if encrypted and not raw.decrypt(password or ""):
        return PdfInfo(pages=0, encrypted=True, size_bytes=size)  # metadata unreadable without the password
    m = raw.metadata
    created = ""
    if m and m.creation_date:
        created = m.creation_date.isoformat() if isinstance(m.creation_date, datetime) else str(m.creation_date)
    return PdfInfo(
        pages=len(raw.pages), encrypted=encrypted, size_bytes=size,
        title=(m.title or "") if m else "", author=(m.author or "") if m else "",
        subject=(m.subject or "") if m else "", producer=(m.producer or "") if m else "", created=created,
    )


# --------------------------------------------------------------------------- extract / clean
def extract_pages(src: Source, *, password: str | None = None, clean: bool = True,
                  page_range: tuple[int, int] | None = None) -> Pages:
    """[(page_no, text)], 1-based. `page_range=(start, end)` inclusive. Pages without text are kept as ''
    so page numbers stay aligned with the real document (citations!)."""
    reader = _open(src, password)
    total = len(reader.pages)
    start, end = page_range or (1, total)
    pages: Pages = []
    for n in range(max(1, start), min(end, total) + 1):
        try:
            text = reader.pages[n - 1].extract_text() or ""
        except Exception:  # a single broken page must not lose the whole document
            text = ""
        pages.append((n, text))
    return clean_pages(pages) if clean else pages


def looks_scanned(src: Source, *, sample: int = 5, min_chars_per_page: int = 25) -> bool:
    """True if the first few pages have (almost) no text => image-only PDF that needs OCR."""
    pages = extract_pages(src, clean=False, page_range=(1, sample))
    if not pages:
        return False
    return sum(len(t.strip()) for _, t in pages) / len(pages) < min_chars_per_page


def clean_pages(pages: Pages, *, repeat_ratio: float = 0.5) -> Pages:
    """Remove noise that pollutes embeddings:
      * lines repeated on >= `repeat_ratio` of pages (running headers/footers, "Confidential"),
      * bare page numbers ("7", "Page 7 of 30", "- 7 -"),
      * end-of-line hyphenation ("informa-\\ntion" -> "information"),
    Only applied to documents of 3+ pages (with fewer, "repeated" is not meaningful)."""
    if not pages:
        return pages
    page_no = re.compile(r"^\s*(page\s+)?\d+(\s*(of|/)\s*\d+)?\s*$|^\s*[-–]\s*\d+\s*[-–]\s*$", re.I)
    repeated: set[str] = set()
    if len(pages) >= 3:
        counts = Counter(
            ln.strip() for _, t in pages for ln in set(t.splitlines()) if 3 <= len(ln.strip()) <= 120
        )
        repeated = {ln for ln, c in counts.items() if c / len(pages) >= repeat_ratio}
    out: Pages = []
    for n, text in pages:
        lines = [ln for ln in text.splitlines() if ln.strip() not in repeated and not page_no.match(ln)]
        cleaned = re.sub(r"(\w)-\n(\w)", r"\1\2", "\n".join(lines))
        out.append((n, cleaned.strip()))
    return out


def extract_text(src: Source, **kw) -> str:
    return "\n\n".join(t for _, t in extract_pages(src, **kw) if t)


# --------------------------------------------------------------------------- management (write PDFs)
def extract_range(src: Source, start: int, end: int, out_path: str | Path, *, password: str | None = None) -> Path:
    """Copy pages start..end (1-based, inclusive) into a new PDF."""
    reader = _open(src, password)
    if not 1 <= start <= end <= len(reader.pages):
        raise PdfError(f"Page range {start}-{end} is outside 1-{len(reader.pages)}")
    writer = PdfWriter()
    for i in range(start - 1, end):
        writer.add_page(reader.pages[i])
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    return out


def split(src: Source, out_dir: str | Path, *, pages_per_file: int = 50, password: str | None = None) -> list[Path]:
    """Split a huge PDF into `<stem>_part01.pdf`, ... Keeps each part small enough to ingest/preview."""
    if pages_per_file < 1:
        raise PdfError("pages_per_file must be >= 1")
    total = len(_open(src, password).pages)
    stem = Path(src).stem if not isinstance(src, bytes) else "document"
    out = []
    for i, start in enumerate(range(1, total + 1, pages_per_file), start=1):
        end = min(start + pages_per_file - 1, total)
        out.append(extract_range(src, start, end, Path(out_dir) / f"{stem}_part{i:02d}.pdf", password=password))
    return out


def merge(sources: Iterable[Source], out_path: str | Path) -> Path:
    """Concatenate several PDFs into one."""
    writer = PdfWriter()
    for s in sources:
        for page in _open(s).pages:
            writer.add_page(page)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        writer.write(f)
    return out
