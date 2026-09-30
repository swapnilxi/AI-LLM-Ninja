"""File-type registry: the ONE place that says which file types the RAG understands.

HOW TO ADD A FILE TYPE (backend)
  1. write `app/utils/<type>.py` with `extract_text(path)` (and `validate(data)` if the format has a magic header);
     for page-aware formats return [(page, text)] like pdf.extract_pages;
  2. register it in REGISTRY below (extension, label, mime, extract function, optional validator);
  3. mirror it in the frontend: rag-ui/utils/files/filetypes.ts  (extension list, label, magic-byte check);
  4. add a sample file to rag-data/ and a test in tests/test_filetypes.py.
Ingestion (app/ingestion), uploads (app/main.py) and the UI all read from here - nothing else needs editing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import docx, html, pdf, tabular

Section = tuple[Optional[int], str]  # (page number or None, text)


class FileValidationError(ValueError):
    """Safe to show to the user (bad name, wrong type, too big, corrupt...)."""


class FileTooLarge(FileValidationError):
    pass


@dataclass(frozen=True)
class FileType:
    ext: tuple[str, ...]
    label: str
    mime: str
    extract: Callable[[Path], list[Section]]
    validate: Optional[Callable[[bytes], object]] = None  # raises on a corrupt / mislabelled file
    magic: bytes = b""  # cheap header check used before full validation


def _text(path: Path) -> list[Section]:
    return [(None, path.read_bytes().decode("utf-8", errors="replace"))]


def _pdf_extract(path: Path) -> list[Section]:
    pages = pdf.extract_pages(path)
    if pages and not any(t.strip() for _, t in pages) and pdf.looks_scanned(path):
        raise pdf.PdfError("PDF has no text layer (scanned images). Run OCR first, e.g. `ocrmypdf in.pdf out.pdf`")
    return list(pages)


REGISTRY: dict[str, FileType] = {}
for _t in (
    FileType((".txt", ".log"), "Text", "text/plain", _text),
    FileType((".md", ".markdown", ".rst"), "Markdown", "text/markdown", _text),
    FileType((".pdf",), "PDF", "application/pdf", _pdf_extract, pdf.validate, b"%PDF"),
    FileType((".docx",), "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             lambda p: [(None, docx.extract_text(p))], docx.validate, b"PK\x03\x04"),
    FileType((".html", ".htm"), "HTML", "text/html", lambda p: [(None, html.extract_text(p))]),
    FileType((".csv",), "CSV", "text/csv", lambda p: [(None, tabular.csv_to_text(p))]),
    FileType((".json",), "JSON", "application/json", lambda p: [(None, tabular.json_to_text(p))]),
):
    for _e in _t.ext:
        REGISTRY[_e] = _t

SUPPORTED = set(REGISTRY)


def file_type(name: str) -> FileType | None:
    return REGISTRY.get(Path(name).suffix.lower())


def safe_filename(name: str) -> str:
    """Strip any directory part (path traversal) and characters that cause trouble on disk / in URLs."""
    clean = re.sub(r"[^\w.\- ]", "_", Path(name.replace("\\", "/")).name).strip(". ")
    if not clean:
        raise FileValidationError("Invalid file name")
    return clean


def validate_upload(filename: str, data: bytes, *, max_mb: int = 25) -> str:
    """Full pre-save check for an uploaded file. Returns the safe file name to store it under."""
    name = safe_filename(filename or "")
    ft = file_type(name)
    if ft is None:
        raise FileValidationError(f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED))}")
    if not data:
        raise FileValidationError(f"{name} is empty")
    if len(data) > max_mb * 1024 * 1024:
        raise FileTooLarge(f"{name} exceeds {max_mb} MB")
    if ft.magic and ft.magic not in data[:1024]:
        raise FileValidationError(f"{name} is not a real {ft.label} file (wrong file header)")
    if ft.validate:
        try:
            ft.validate(data)
        except ValueError as e:  # PdfError / DocxError are ValueErrors
            raise FileValidationError(f"{name}: {e}") from e
    return name


def extract(path: Path) -> list[Section]:
    """Text of any supported file as [(page | None, text)]."""
    ft = file_type(path.name)
    if ft is None:
        raise ValueError(f"Unsupported file type: {path.suffix}")
    return ft.extract(path)


def describe(path: Path) -> dict:
    """Type-specific metadata for the UI (pages, title, author...)."""
    ft = file_type(path.name)
    info: dict = {"name": path.name, "type": ft.label if ft else "Unknown", "mime": ft.mime if ft else "",
                  "size": path.stat().st_size}
    try:
        if path.suffix.lower() == ".pdf":
            i = pdf.read_info(path)
            info.update(pages=i.pages, title=i.title, author=i.author, created=i.created, encrypted=i.encrypted,
                        scanned=pdf.looks_scanned(path) if i.pages and not i.encrypted else False)
        elif path.suffix.lower() == ".docx":
            d = docx.read_info(path)
            info.update(title=d.title, author=d.author, created=d.created, paragraphs=d.paragraphs, tables=d.tables)
    except ValueError as e:
        info["error"] = str(e)
    return info
