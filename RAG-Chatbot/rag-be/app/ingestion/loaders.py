"""Turn files into text: [(page_number | None, text), ...].

The per-format code lives in app/utils/ (pdf.py, docx.py, html.py, tabular.py) and is registered in
app/utils/filetypes.py; this module just exposes it under the names the ingestion code uses.
"""
from __future__ import annotations

from pathlib import Path

from ..utils.filetypes import SUPPORTED
from ..utils.filetypes import extract as _extract

Section = tuple[int | None, str]


def load_file(path: Path) -> list[Section]:
    return _extract(path)


__all__ = ["SUPPORTED", "Section", "load_file"]
