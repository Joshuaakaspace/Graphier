"""Chronology across every vault source, structured or not.

Every DATE mention — in a Markdown note, a PDF, a DOCX, an HTML page —
anchors an event: the sentence it appears in, the entities that share
that sentence, and the source it came from. Sorted, that is the vault's
timeline, with the same sentence-level provenance as everything else.
"""

from __future__ import annotations

import re
from typing import Any

from .extraction import ExtractionService
from .graph import _sentence_at, collect_domain
from .vault import Vault

_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b")
_MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"),
            ("april", "apr"), ("may",), ("june", "jun"), ("july", "jul"),
            ("august", "aug"), ("september", "sep", "sept"), ("october", "oct"),
            ("november", "nov"), ("december", "dec"),
        ]
    )
    for m in names
}
_MONTH_RE = re.compile(
    r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\w*\s+(\d{4})\b",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _parse_date(sentence: str, fallback: str) -> tuple[tuple[int, int, int], str] | None:
    """Best (sort_key, display) date found in the sentence, or from the
    DATE entity text itself."""
    m = _ISO_RE.search(sentence)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return (y, mo, d), m.group(0)
    m = _MONTH_RE.search(sentence)
    if m:
        return (int(m.group(2)), _MONTHS[m.group(1).lower()], 0), m.group(0)
    m = _DMY_RE.search(sentence)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000 if y < 50 else 1900
        day, month = (a, b) if b <= 12 else (b, a)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (y, month, day), m.group(0)
    m = _YEAR_RE.search(sentence) or _YEAR_RE.search(fallback)
    if m:
        return (int(m.group(1)), 0, 0), m.group(1)
    return None


def build_timeline(vault: Vault, extractor: ExtractionService) -> list[dict[str, Any]]:
    patterns, templates = collect_domain(vault)
    events: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    for meta in vault.list_notes():
        content = vault.read(meta.id)
        result = extractor.extract(content, patterns, templates)
        entities = result["entities"]

        for ent in entities:
            if ent["label"] != "DATE":
                continue
            sentence = _sentence_at(content, ent["start"])
            parsed = _parse_date(sentence, ent["text"])
            if parsed is None or not sentence:
                continue
            sort_key, display = parsed
            key = (sort_key, sentence, meta.id)
            if key in seen:
                continue
            seen.add(key)

            # Entities sharing the sentence give the event its cast.
            lo = content.find(sentence)
            hi = lo + len(sentence) if lo >= 0 else -1
            cast = [
                {"text": e["text"], "label": e["label"]}
                for e in entities
                if e["label"] != "DATE" and lo <= e["start"] < hi
            ] if lo >= 0 else []

            events.append(
                {
                    "date": display,
                    "sort_key": list(sort_key),
                    "year": sort_key[0],
                    "sentence": sentence,
                    "note": meta.id,
                    "title": meta.title,
                    "kind": meta.kind,
                    "entities": cast[:6],
                }
            )

    events.sort(key=lambda e: (e["sort_key"], e["note"]))
    return events
