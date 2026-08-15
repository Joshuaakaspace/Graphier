"""Entity and relation extraction via Semantica's deterministic pipeline.

Uses the pattern-based extractors (no ML models, no LLM) so the walking
skeleton runs anywhere. Results are cached by content hash: re-extracting
an unchanged note is free, and editing a note invalidates only that note.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any

os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

from semantica.semantic_extract import NERExtractor, RelationExtractor  # noqa: E402

# Wiki-links are explicit user-drawn edges; they bypass extraction confidence.
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]*)?\]\]")

_MARKDOWN_CHARS = set("#*_`>[]()|")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)


def _mask_for_extraction(text: str) -> str:
    """Shadow copy for the extractors: same length (so spans map back to the
    original), but with markdown syntax spaced out, newlines turned into
    sentence breaks (the pattern extractors join words across any whitespace),
    and wiki-links blanked entirely — those are explicit edges, not
    extraction targets.
    """
    chars = list(text)
    for m in _WIKILINK_RE.finditer(text):
        for i in range(m.start(), m.end()):
            chars[i] = " "
    # Fenced code blocks (including ```datalog rules) aren't prose.
    for m in _CODE_BLOCK_RE.finditer(text):
        for i in range(m.start(), m.end()):
            if chars[i] != "\n":
                chars[i] = " "
    # Blank heading lines: the heading is the note's own title (it becomes a
    # NOTE node in the graph), not a mention to extract.
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#"):
            for i in range(pos, pos + len(line.rstrip("\n"))):
                chars[i] = " "
        pos += len(line)
    for i, c in enumerate(chars):
        if c == "\n":
            chars[i] = "."
        elif c in _MARKDOWN_CHARS:
            chars[i] = " "
    return "".join(chars)


_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_-]*)\}")


def _match_relation_templates(
    masked: str, entities: list, templates: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Match domain relation templates like '{TICKET} blocks {PROJECT}'.

    Placeholders match any entity of that type already extracted from this
    text; literal words in between match loosely across whitespace. The
    first placeholder is the subject, the second the object.
    """
    by_label: dict[str, dict[str, Any]] = {}
    for e in entities:
        by_label.setdefault(e.label, {})[e.text] = e

    found: list[dict[str, Any]] = []
    for predicate, template in templates:
        parts = _PLACEHOLDER_RE.split(template)
        # Exactly two placeholders: [prefix, TYPE1, middle, TYPE2, suffix]
        if len(parts) != 5:
            continue
        subj_pool = by_label.get(parts[1].upper())
        obj_pool = by_label.get(parts[3].upper())
        if not subj_pool or not obj_pool:
            continue

        def literal(fragment: str) -> str:
            words = fragment.split()
            return (r"\s+".join(re.escape(w) for w in words)) if words else ""

        # Components must appear in order within one sentence (masked
        # newlines are '.'), with filler words allowed between them:
        # '{TICKET} blocks {PROJECT}' matches 'ENG-42 blocks the Icarus
        # Project rollout'.
        gap = r"[^.]*?"
        middle = literal(parts[2])
        pattern = (
            (literal(parts[0]) + gap if parts[0].strip() else "")
            + f"(?P<subj>{'|'.join(re.escape(t) for t in subj_pool)})"
            + (gap + middle + gap if middle else gap)
            + f"(?P<obj>{'|'.join(re.escape(t) for t in obj_pool)})"
            + (gap + literal(parts[4]) if parts[4].strip() else "")
        )
        try:
            compiled = re.compile(pattern)
        except re.error:
            continue
        for m in compiled.finditer(masked):
            subj = subj_pool[m.group("subj")]
            obj = obj_pool[m.group("obj")]
            found.append(
                {
                    "subject": subj.text,
                    "subject_label": subj.label,
                    "predicate": predicate.lower(),
                    "object": obj.text,
                    "object_label": obj.label,
                    "confidence": 0.9,
                    "start": m.start(),
                }
            )
    return found


class _DomainEntity:
    """Entity-shaped match from a user-defined domain pattern."""

    def __init__(self, text: str, label: str, start: int, end: int):
        self.text = text
        self.label = label
        self.start_char = start
        self.end_char = end
        self.confidence = 0.9  # explicit user pattern beats generic heuristics


class ExtractionService:
    def __init__(self, method: str = "pattern"):
        self._ner = NERExtractor(method=method)
        self._relations = RelationExtractor(method=method)
        self._cache: dict[str, dict[str, Any]] = {}

    def extract(
        self,
        text: str,
        domain_patterns: dict[str, str] | None = None,
        relation_templates: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        domain_patterns = domain_patterns or {}
        relation_templates = relation_templates or []
        key = hashlib.sha256(
            (
                text
                + "\x00"
                + repr(sorted(domain_patterns.items()))
                + "\x00"
                + repr(sorted(relation_templates))
            ).encode("utf-8")
        ).hexdigest()
        if key in self._cache:
            return self._cache[key]

        masked = _mask_for_extraction(text)

        # Domain types first: explicit user patterns win over generic NER.
        domain_entities: list[_DomainEntity] = []
        for label, pattern in domain_patterns.items():
            try:
                compiled = re.compile(pattern)
            except re.error:
                continue  # a bad pattern contributes nothing
            for m in compiled.finditer(masked):
                if m.start() < m.end():
                    domain_entities.append(
                        _DomainEntity(text[m.start() : m.end()], label, m.start(), m.end())
                    )

        entities = self._ner.extract(masked)
        for e in entities:
            # Some upstream patterns capture trailing punctuation — trim it.
            while e.end_char > e.start_char and text[e.end_char - 1] in ".,;:!?":
                e.end_char -= 1
            e.text = text[e.start_char : e.end_char]
        # NER entities overlapping a domain match yield to it.
        entities = domain_entities + [
            e
            for e in entities
            if not any(
                d.start_char < e.end_char and e.start_char < d.end_char
                for d in domain_entities
            )
        ]
        # Dedupe overlapping spans, keep the longest match at each position.
        entities = self._dedupe(entities)
        relations = self._relations.extract(masked, entities) if entities else []
        custom_relations = _match_relation_templates(masked, entities, relation_templates)

        result = {
            "entities": [
                {
                    "text": text[e.start_char : e.end_char],
                    "label": e.label,
                    "start": e.start_char,
                    "end": e.end_char,
                    "confidence": e.confidence,
                }
                for e in entities
            ],
            "wikilinks": [
                {"text": m.group(1).strip(), "start": m.start(), "end": m.end()}
                for m in _WIKILINK_RE.finditer(text)
            ],
            "relations": [
                {
                    "subject": r.subject.text,
                    "subject_label": r.subject.label,
                    "predicate": r.predicate,
                    "object": r.object.text,
                    "object_label": r.object.label,
                    "confidence": r.confidence,
                    # Anchor for sentence-level provenance.
                    "start": min(r.subject.start_char, r.object.start_char),
                }
                for r in relations
            ]
            + custom_relations,
        }
        self._cache[key] = result
        return result

    @staticmethod
    def _dedupe(entities: list) -> list:
        entities = sorted(entities, key=lambda e: (e.start_char, -(e.end_char - e.start_char)))
        kept: list = []
        for e in entities:
            if kept and e.start_char < kept[-1].end_char:
                continue
            kept.append(e)
        return kept
