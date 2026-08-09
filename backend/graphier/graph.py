"""Vault-wide graph aggregation.

Derives a small knowledge graph from per-note extractions: nodes are
entities deduped across notes (by normalized text + type), edges come from
extracted relations and explicit [[wiki-links]]. Every node and edge keeps
the list of notes it came from — that provenance is what the "why" panel
builds on in later phases.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .extraction import ExtractionService
from .vault import Vault


def _node_key(text: str, label: str) -> str:
    return f"{label}:{text.strip().lower()}"


def build_graph(vault: Vault, extractor: ExtractionService) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple, dict[str, Any]] = {}
    note_titles: dict[str, str] = {}

    for meta in vault.list_notes():
        note_titles[meta.id] = meta.title
        result = extractor.extract(vault.read(meta.id))

        for ent in result["entities"]:
            key = _node_key(ent["text"], ent["label"])
            node = nodes.setdefault(
                key,
                {"id": key, "text": ent["text"], "label": ent["label"], "count": 0, "notes": []},
            )
            node["count"] += 1
            if meta.id not in node["notes"]:
                node["notes"].append(meta.id)

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
                },
            )
            if meta.id not in edge["notes"]:
                edge["notes"].append(meta.id)

        # Wiki-links: user-drawn edges from this note to the linked concept.
        note_node = nodes.setdefault(
            _node_key(meta.title, "NOTE"),
            {"id": _node_key(meta.title, "NOTE"), "text": meta.title, "label": "NOTE",
             "count": 0, "notes": [meta.id]},
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
                },
            )
            if meta.id not in edge["notes"]:
                edge["notes"].append(meta.id)

    by_label: dict[str, int] = defaultdict(int)
    for node in nodes.values():
        by_label[node["label"]] += 1

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "note_titles": note_titles,
        "summary": {
            "notes": len(note_titles),
            "nodes": len(nodes),
            "edges": len(edges),
            "by_label": dict(by_label),
        },
    }


def _find_or_create_link_target(nodes: dict[str, dict[str, Any]], text: str) -> str:
    # Link to an existing extracted entity of the same name if there is one,
    # regardless of type; otherwise create a CONCEPT node.
    lowered = text.strip().lower()
    for key, node in nodes.items():
        if node["text"].strip().lower() == lowered:
            return key
    key = _node_key(text, "CONCEPT")
    nodes[key] = {"id": key, "text": text, "label": "CONCEPT", "count": 1, "notes": []}
    return key
