"""Hybrid vault search: lexical TF-IDF + knowledge-graph awareness.

Pure numpy TF-IDF with cosine ranking, then graph-boosted: a note that
mentions an entity whose name matches the query outranks a note that
merely shares vocabulary. Matching entities are returned alongside note
hits so the UI can offer their entity pages directly.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_ENTITY_BOOST = 0.35


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

    # ---- TF-IDF cosine over note bodies ----
    doc_tokens = {note_id: _tokens(content) for note_id, content in notes.items()}
    doc_freq: Counter = Counter()
    for toks in doc_tokens.values():
        doc_freq.update(set(toks))
    n_docs = len(notes)

    def idf(term: str) -> float:
        return math.log((n_docs + 1) / (doc_freq[term] + 1)) + 1

    def vectorize(toks: list[str]) -> dict[str, float]:
        counts = Counter(toks)
        total = len(toks) or 1
        return {t: (c / total) * idf(t) for t, c in counts.items()}

    query_vec = vectorize(query_tokens)
    query_norm = math.sqrt(sum(w * w for w in query_vec.values())) or 1.0

    scored = []
    for note_id, toks in doc_tokens.items():
        doc_vec = vectorize(toks)
        dot = sum(query_vec[t] * doc_vec.get(t, 0.0) for t in query_vec)
        doc_norm = math.sqrt(sum(w * w for w in doc_vec.values())) or 1.0
        score = dot / (query_norm * doc_norm) + boosted_notes.get(note_id, 0.0)
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
