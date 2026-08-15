"""Vault-wide graph aggregation.

Derives a small knowledge graph from per-note extractions: nodes are
entities deduped across notes (by normalized text + type), edges come from
extracted relations and explicit [[wiki-links]]. Every node and edge keeps
sentence-level evidence — the note and the exact sentence that produced
it — which is what the "why" panel and entity pages surface.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .extraction import ExtractionService
from .vault import Vault

# ```datalog blocks in any note program the vault's reasoner.
_RULE_BLOCK_RE = re.compile(r"```datalog\s*\n(.*?)```", re.DOTALL)

# ```domain blocks declare custom entity types: "LABEL: regex" per line.
_DOMAIN_BLOCK_RE = re.compile(r"```domain\s*\n(.*?)```", re.DOTALL)
_DOMAIN_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.+)$")

# The built-in vocabulary; domain types may not shadow these.
_BUILTIN_LABELS = {"PERSON", "ORG", "GPE", "DATE", "NOTE", "CONCEPT"}

_MAX_EVIDENCE = 12  # per node/edge, keeps payloads bounded


def _node_key(text: str, label: str) -> str:
    return f"{label}:{text.strip().lower()}"


def _sentence_at(content: str, pos: int) -> str:
    """The sentence (bounded by newline or period) containing pos."""
    if pos < 0 or pos >= len(content):
        return ""
    start = pos
    while start > 0 and content[start - 1] not in ".\n":
        start -= 1
    end = pos
    while end < len(content) and content[end] not in ".\n":
        end += 1
    if end < len(content) and content[end] == ".":
        end += 1
    return content[start:end].strip().lstrip("#").strip()


def _add_evidence(item: dict[str, Any], note_id: str, sentence: str) -> None:
    if len(item["evidence"]) >= _MAX_EVIDENCE:
        return
    entry = {"note": note_id, "sentence": sentence}
    if entry not in item["evidence"]:
        item["evidence"].append(entry)


def build_graph(vault: Vault, extractor: ExtractionService) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple, dict[str, Any]] = {}
    note_titles: dict[str, str] = {}
    custom_rules: list[dict[str, str]] = []

    # First pass: read everything, collect vault-wide rules and domain types.
    contents: dict[str, str] = {}
    domain_types: list[dict[str, str]] = []
    domain_patterns: dict[str, str] = {}
    for meta in vault.list_notes():
        note_titles[meta.id] = meta.title
        content = vault.read(meta.id)
        contents[meta.id] = content
        for block in _RULE_BLOCK_RE.findall(content):
            for line in block.splitlines():
                line = line.strip()
                if line and ":-" in line and not line.startswith("%"):
                    custom_rules.append({"rule": line, "note": meta.id})
        for block in _DOMAIN_BLOCK_RE.findall(content):
            for line in block.splitlines():
                match = _DOMAIN_LINE_RE.match(line.strip())
                if not match:
                    continue
                label = match.group(1).upper()
                if label in _BUILTIN_LABELS or label in domain_patterns:
                    continue
                domain_patterns[label] = match.group(2).strip()
                domain_types.append(
                    {"label": label, "pattern": match.group(2).strip(), "note": meta.id}
                )

    for meta in vault.list_notes():
        content = contents[meta.id]
        result = extractor.extract(content, domain_patterns)

        for ent in result["entities"]:
            key = _node_key(ent["text"], ent["label"])
            node = nodes.setdefault(
                key,
                {"id": key, "text": ent["text"], "label": ent["label"], "count": 0,
                 "notes": [], "evidence": []},
            )
            node["count"] += 1
            if meta.id not in node["notes"]:
                node["notes"].append(meta.id)
            _add_evidence(node, meta.id, _sentence_at(content, ent["start"]))

        for rel in result["relations"]:
            src = _node_key(rel["subject"], rel["subject_label"])
            dst = _node_key(rel["object"], rel["object_label"])
            if src == dst or src not in nodes or dst not in nodes:
                continue
            key = (src, rel["predicate"], dst)
            edge = edges.setdefault(
                key,
                {
                    "source": src,
                    "target": dst,
                    "predicate": rel["predicate"],
                    "origin": "extracted",
                    "confidence": rel["confidence"],
                    "notes": [],
                    "evidence": [],
                },
            )
            if meta.id not in edge["notes"]:
                edge["notes"].append(meta.id)
            _add_evidence(edge, meta.id, _sentence_at(content, rel["start"]))

        # Wiki-links: user-drawn edges from this note to the linked concept.
        note_node = nodes.setdefault(
            _node_key(meta.title, "NOTE"),
            {"id": _node_key(meta.title, "NOTE"), "text": meta.title, "label": "NOTE",
             "count": 0, "notes": [meta.id], "evidence": []},
        )
        note_node["count"] += 1
        for link in result["wikilinks"]:
            target_key = _find_or_create_link_target(nodes, link["text"])
            key = (note_node["id"], "links_to", target_key)
            edge = edges.setdefault(
                key,
                {
                    "source": note_node["id"],
                    "target": target_key,
                    "predicate": "links_to",
                    "origin": "manual",
                    "confidence": 1.0,
                    "notes": [],
                    "evidence": [],
                },
            )
            if meta.id not in edge["notes"]:
                edge["notes"].append(meta.id)
            _add_evidence(edge, meta.id, _sentence_at(content, link["start"]))

    by_label: dict[str, int] = defaultdict(int)
    for node in nodes.values():
        by_label[node["label"]] += 1

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "note_titles": note_titles,
        "custom_rules": custom_rules,
        "domain_types": domain_types,
        "summary": {
            "notes": len(note_titles),
            "nodes": len(nodes),
            "edges": len(edges),
            "by_label": dict(by_label),
        },
    }


def collect_domain_patterns(vault: Vault) -> dict[str, str]:
    """Vault-wide domain types without running extraction (cheap scan)."""
    patterns: dict[str, str] = {}
    for meta in vault.list_notes():
        for block in _DOMAIN_BLOCK_RE.findall(vault.read(meta.id)):
            for line in block.splitlines():
                match = _DOMAIN_LINE_RE.match(line.strip())
                if match:
                    label = match.group(1).upper()
                    if label not in _BUILTIN_LABELS and label not in patterns:
                        patterns[label] = match.group(2).strip()
    return patterns


def entity_page(graph: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Everything the vault knows about one entity, with evidence."""
    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if node is None:
        return None
    titles = graph["note_titles"]
    display = {n["id"]: n["text"] for n in graph["nodes"]}

    relations = []
    for edge in graph["edges"]:
        if node_id not in (edge["source"], edge["target"]):
            continue
        is_subject = edge["source"] == node_id
        other_id = edge["target"] if is_subject else edge["source"]
        relations.append(
            {
                "predicate": edge["predicate"],
                "direction": "out" if is_subject else "in",
                "other": display.get(other_id, other_id),
                "other_id": other_id,
                "origin": edge["origin"],
                "confidence": edge["confidence"],
                "evidence": [
                    {**ev, "title": titles.get(ev["note"], ev["note"])}
                    for ev in edge["evidence"]
                ],
            }
        )

    return {
        "node": node,
        "mentions": [
            {**ev, "title": titles.get(ev["note"], ev["note"])} for ev in node["evidence"]
        ],
        "relations": relations,
    }


def _find_or_create_link_target(nodes: dict[str, dict[str, Any]], text: str) -> str:
    # Link to an existing extracted entity of the same name if there is one,
    # regardless of type; otherwise create a CONCEPT node.
    lowered = text.strip().lower()
    for key, node in nodes.items():
        if node["text"].strip().lower() == lowered:
            return key
    key = _node_key(text, "CONCEPT")
    nodes[key] = {"id": key, "text": text, "label": "CONCEPT", "count": 1,
                  "notes": [], "evidence": []}
    return key
