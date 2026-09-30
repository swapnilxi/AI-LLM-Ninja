"""CSV / JSON utilities: turn structured data into text a retriever can use.

CHECKLIST for structured data
  * CSV: one line per row, "column: value; column: value" so each chunk carries its own column names
    (a bare "12, 4.5, red" row is meaningless once it is separated from the header).
  * JSON: pretty-printed, so chunk boundaries fall on lines. For big JSON arrays prefer one record per chunk.
  * Excel (.xlsx): not built in; export to CSV or add `openpyxl` and reuse `rows_to_text`.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def rows_to_text(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header, body = rows[0], rows[1:]
    return "\n".join("; ".join(f"{h}: {v}" for h, v in zip(header, r) if v) for r in body)


def csv_to_text(src: str | Path | bytes) -> str:
    raw = src.read_bytes() if isinstance(src, Path) else src
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else raw  # utf-8-sig strips Excel's BOM
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return rows_to_text(list(csv.reader(io.StringIO(text), dialect)))


def json_to_text(src: str | Path | bytes) -> str:
    raw = src.read_bytes() if isinstance(src, Path) else src
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
