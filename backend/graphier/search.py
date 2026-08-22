"""Hybrid vault search: lexical BM25 + knowledge-graph awareness.

Pure-Python Okapi BM25 (term-frequency saturation + document-length
normalization), then graph-boosted: a note that mentions an entity whose
name matches the query outranks a note that merely shares vocabulary.
Matching entities are returned alongside note hits so the UI can offer
their entity pages directly.

BM25 raw scores are unbounded, so each score is divided by the query's
best achievable score — every term saturated to its ceiling — mapping it
into [0, 1]. That keeps the flat entity boost and the relevance floor
meaningful regardless of query length.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_ENTITY_BOOST = 0.35

# Okapi BM25 constants: _K1 controls how quickly repeated terms stop
# adding score, _B how strongly long documents are penalized.
_K1 = 1.5
_B = 0.75


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def search(
    query: str,
    notes: dict[str, str],
    note_titles: dict[str, str],
    graph: dict[str, Any],
    limit: int = 10,
) -> dict[str, Any]:
    query_tokens = _tokens(query)
    if not query_tokens or not notes:
        return {"results": [], "entities": []}

    # ---- entity matches: graph-aware half of the ranking ----
    query_lower = " ".join(query_tokens)
    matched_entities = []
    boosted_notes: dict[str, float] = {}
    for node in graph["nodes"]:
        if node["label"] == "NOTE":
            continue
        node_lower = " ".join(_tokens(node["text"]))
        if not node_lower:
            continue
        if node_lower in query_lower or query_lower in node_lower:
            matched_entities.append(
                {"id": node["id"], "text": node["text"], "label": node["label"]}
            )
            for note_id in node["notes"]:
                boosted_notes[note_id] = boosted_notes.get(note_id, 0.0) + _ENTITY_BOOST

    # ---- BM25 over note bodies ----
    doc_tokens = {note_id: _tokens(content) for note_id, content in notes.items()}
    doc_freq: Counter = Counter()
    for toks in doc_tokens.values():
        doc_freq.update(set(toks))
    n_docs = len(notes)
    avg_len = sum(len(toks) for toks in doc_tokens.values()) / n_docs or 1.0

    def idf(term: str) -> float:
        df = doc_freq[term]
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    query_terms = set(query_tokens)
    best_possible = sum(idf(t) * (_K1 + 1) for t in query_terms) or 1.0

    scored = []
    for note_id, toks in doc_tokens.items():
        counts = Counter(toks)
        length_norm = _K1 * (1 - _B + _B * len(toks) / avg_len)
        raw = sum(
            idf(t) * counts[t] * (_K1 + 1) / (counts[t] + length_norm)
            for t in query_terms
            if counts[t]
        )
        score = raw / best_possible + boosted_notes.get(note_id, 0.0)
        if score > 0.01:
            scored.append((score, note_id))
    scored.sort(reverse=True)

    results = []
    for score, note_id in scored[:limit]:
        results.append(
            {
                "id": note_id,
                "title": note_titles.get(note_id, note_id),
                "score": round(score, 4),
                "snippet": _snippet(notes[note_id], query_tokens),
            }
        )
    return {"results": results, "entities": matched_entities[:5]}


def _snippet(content: str, query_tokens: list[str], width: int = 130) -> str:
    lowered = content.lower()
    pos = -1
    for token in query_tokens:
        pos = lowered.find(token)
        if pos >= 0:
            break
    if pos < 0:
        pos = 0
    start = max(0, pos - width // 3)
    snippet = content[start : start + width].replace("\n", " ").strip().lstrip("#").strip()
    return ("…" if start > 0 else "") + snippet + ("…" if start + width < len(content) else "")
