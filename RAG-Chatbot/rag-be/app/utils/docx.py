"""DOCX (Word) utilities. Standard library only: a .docx is a zip of XML files, no `python-docx` needed.

CHECKLIST when building the next RAG (what to decide / do for Word files)
  1. VALIDATE uploads ...... `validate(data)`       zip magic + must contain word/document.xml
  2. EXTRACT text .......... `extract_text(path)`   headings become markdown (#, ##) so chunks keep structure;
                                                    tables become "cell | cell" rows (otherwise they vanish)
  3. READ metadata ......... `read_info(path)`      title, author, created, paragraph/table counts
  4. FRONTEND mirror ....... rag-be/../rag-ui/utils/files/docx.ts
Not handled (add if you need them): images/charts, headers/footers, footnotes, tracked changes (deleted text is
skipped, inserted text is kept), legacy binary .doc (convert with LibreOffice: `soffice --headless --convert-to docx`).
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ZIP_MAGIC = b"PK\x03\x04"
Source = Union[str, Path, bytes]


class DocxError(ValueError):
    """A DOCX problem that is safe to show to the user."""


@dataclass
class DocxInfo:
    title: str = ""
    author: str = ""
    created: str = ""
    paragraphs: int = 0
    tables: int = 0


def _open(src: Source) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(io.BytesIO(src) if isinstance(src, bytes) else str(src))
    except (zipfile.BadZipFile, OSError) as e:
        raise DocxError("Not a valid .docx (not a zip archive)") from e
    if "word/document.xml" not in z.namelist():
        raise DocxError("Not a Word document (word/document.xml missing) - is it .xlsx/.pptx renamed?")
    return z


def validate(src: Source, *, max_uncompressed_mb: int = 200) -> DocxInfo:
    """Raise DocxError unless this is a readable .docx. Also guards against zip bombs."""
    head = src[:4] if isinstance(src, bytes) else Path(src).read_bytes()[:4]
    if head != ZIP_MAGIC:
        raise DocxError("File does not look like a .docx (missing zip header)")
    with _open(src) as z:
        if sum(i.file_size for i in z.infolist()) > max_uncompressed_mb * 1024 * 1024:
            raise DocxError(f"Document expands to more than {max_uncompressed_mb} MB (possible zip bomb)")
    return read_info(src)


def read_info(src: Source) -> DocxInfo:
    with _open(src) as z:
        info = DocxInfo()
        if "docProps/core.xml" in z.namelist():
            core = ET.fromstring(z.read("docProps/core.xml"))
            for el in core:
                tag = el.tag.split("}")[-1]
                if tag == "title":
                    info.title = el.text or ""
                elif tag == "creator":
                    info.author = el.text or ""
                elif tag == "created":
                    info.created = el.text or ""
        body = ET.fromstring(z.read("word/document.xml")).find(f"{W}body")
        if body is not None:
            info.paragraphs = len(body.findall(f"{W}p"))
            info.tables = len(body.findall(f"{W}tbl"))
    return info


def _para_text(p: ET.Element) -> str:
    parts = []
    for node in p.iter():
        if node.tag == f"{W}t" and node.text:
            parts.append(node.text)
        elif node.tag in (f"{W}tab",):
            parts.append("\t")
        elif node.tag in (f"{W}br", f"{W}cr"):
            parts.append("\n")
    return "".join(parts)


def _heading_level(p: ET.Element) -> int:
    style = p.find(f"{W}pPr/{W}pStyle")
    val = style.get(f"{W}val", "") if style is not None else ""
    m = re.fullmatch(r"(?:Heading|heading)\s*(\d)", val)
    return int(m.group(1)) if m else (1 if val == "Title" else 0)


def extract_text(src: Source) -> str:
    """Document text in reading order: headings as markdown, tables as `a | b | c` rows."""
    with _open(src) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(f"{W}body")
    if body is None:
        return ""
    out: list[str] = []
    for el in body:
        if el.tag == f"{W}p":
            text = _para_text(el).strip()
            if not text:
                continue
            level = _heading_level(el)
            out.append(f"{'#' * level} {text}" if level else text)
        elif el.tag == f"{W}tbl":
            for row in el.iter(f"{W}tr"):
                cells = [" ".join(_para_text(p).strip() for p in c.iter(f"{W}p")).strip() for c in row.findall(f"{W}tc")]
                if any(cells):
                    out.append(" | ".join(cells))
            out.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
