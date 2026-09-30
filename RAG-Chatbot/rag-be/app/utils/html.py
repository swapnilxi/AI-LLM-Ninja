"""HTML utilities (standard library only): visible text + title, without scripts/styles/navigation noise.

CHECKLIST for HTML sources
  * `extract_text(html)` keeps paragraph/heading/list/table-row breaks so chunking still has structure.
  * scripts, styles, <nav>, <footer>, <header>, <noscript> are dropped (menus and cookie banners pollute retrieval).
  * For crawling live sites you also want: fetching, robots.txt, dedupe by canonical URL - not covered here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "svg", "template"}
BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "table"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")
            if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
                self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def parse(html: str) -> tuple[str, str]:
    """(title, text)"""
    p = _Extractor()
    p.feed(html)
    text = re.sub(r"[ \t]+", " ", "".join(p.parts))
    return p.title.strip(), re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_text(src: str | Path | bytes) -> str:
    if isinstance(src, Path):
        src = src.read_bytes()
    html = src.decode("utf-8", errors="replace") if isinstance(src, bytes) else src
    return parse(html)[1]
