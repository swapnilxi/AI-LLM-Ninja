"""Entity extraction for the graph. Runs at index time, once per chunk.

`heuristic` (default) is free and instant: capitalised phrases, acronyms, CamelCase and code-like tokens.
`llm` asks the configured model (one call per chunk, so slower and it costs tokens) and falls back to the heuristic
when the model returns nothing usable.
"""
from __future__ import annotations

import re

from .base import MIN_ENTITY_LEN, norm_entity

MAX_ENTITIES = 12
_PHRASE = re.compile(r"[A-Z][A-Za-z0-9&'’-]*(?:\s+(?:of\s+|de\s+)?[A-Z][A-Za-z0-9&'’-]*)*")
_CODEY = re.compile(r"\b[A-Za-z]+[-_][A-Za-z0-9_-]+\b|\b[A-Za-z]+\d+[A-Za-z0-9]*\b")
_STOP = set("""
a an the this that these those it its we our you your they their he she his her i my me us them there here
if when what how why who whom which where while whether then than so but and or nor not no yes also
in on at for to of by with from as into over under about after before between during per via
is are was were be been being has have had do does did can could will would should may might must
please note see example examples however therefore thus hence moreover additionally finally first second third
all any each every some many most more less other another such only just very much
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december
""".split())


def _clean(phrase: str) -> str:
    words = phrase.replace("’", "'").split()
    while words and words[0].lower().rstrip("'s") in _STOP:
        words.pop(0)
    while words and words[-1].lower() in _STOP:
        words.pop()
    return " ".join(words).strip("-'&")


def heuristic_entities(text: str) -> list[str]:
    found: dict[str, str] = {}
    for m in _PHRASE.finditer(text):
        e = _clean(m.group(0))
        if len(e) >= MIN_ENTITY_LEN and e.lower() not in _STOP:
            found.setdefault(norm_entity(e), e)
    for m in _CODEY.finditer(text):
        e = m.group(0)
        if len(e) >= MIN_ENTITY_LEN and e.lower() not in _STOP:
            found.setdefault(norm_entity(e), e)
    return list(found.values())[:MAX_ENTITIES]


def extract_entities(text: str, settings=None, llm=None) -> list[str]:
    if settings is not None and settings.graph_extractor == "llm" and llm is not None:
        from ..rag import ENTITY_PROMPT, parse_entities  # local import: rag imports this package

        try:
            ents = parse_entities(llm.chat([{"role": "system", "content": ENTITY_PROMPT}, {"role": "user", "content": text[:4000]}]))
            if ents:
                return ents
        except Exception:
            pass
    return heuristic_entities(text)
