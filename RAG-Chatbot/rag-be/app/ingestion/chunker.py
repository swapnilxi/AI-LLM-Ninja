"""Recursive character splitter: prefers paragraph, then line, then sentence, then word boundaries."""
from __future__ import annotations

import re

SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split(text: str, size: int, seps: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    if not seps:  # no boundary left: hard cut
        return [text[i : i + size] for i in range(0, len(text), size)]
    sep, rest = seps[0], seps[1:]
    pieces = text.split(sep)
    out: list[str] = []
    for i, piece in enumerate(pieces):
        piece = piece + (sep if i < len(pieces) - 1 else "")
        out.extend(_split(piece, size, rest) if len(piece) > size else [piece])
    return out


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    if not text:
        return []
    chunks: list[str] = []
    cur = ""
    for piece in _split(text, size, SEPARATORS):
        if cur and len(cur) + len(piece) > size:
            chunks.append(cur.strip())
            tail = cur[-overlap:] if overlap else ""
            # start the next chunk on a word boundary so we don't begin mid-word
            cur = tail[tail.find(" ") + 1 :] if " " in tail and not tail.startswith(" ") else tail
        cur += piece
    if cur.strip():
        chunks.append(cur.strip())
    return chunks
