"""Deterministic enrichment over the vault graph.

Everything here is derived — no LLM, fully explainable:

- Inferred connections: Semantica's DatalogReasoner forward-chains Horn
  rules over extracted facts. Explanations ride in the rule head, so every
  inferred edge can say exactly why it exists.
- Link suggestions: entities in one note that other notes also mention.
- Conflicts: the same subject + predicate asserted with different objects
  in different notes.
- Insights: PageRank over the vault graph via Semantica's
  CentralityCalculator — the entities your vault actually revolves around.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any

os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

import networkx as nx  # noqa: E402
from semantica.kg import CentralityCalculator  # noqa: E402
from semantica.reasoning.datalog_reasoner import DatalogReasoner  # noqa: E402

# Rule heads carry every variable needed to explain the inference to the user.
# bridged: X and Y never share a note, but both co-occur with bridge B.
# chained: a 2-hop path through extracted (non-generic) relations.
INFERENCE_RULES = [
    (
        "bridged(X, Y, B, N1, N2) :- comention(X, B, N1), comention(Y, B, N2)",
        "bridged",
        ("X", "Y"),
    ),
    (
        "chained(X, Z, Y, P1, P2) :- rel(X, Y, P1), rel(Y, Z, P2)",
        "chained",
        ("X", "Z"),
    ),
]

# related_to is co-occurrence noise from the pattern extractor, not a claim.
_GENERIC_PREDICATES = {"related_to"}

# Predicates users may reference in their own rules but not redefine as heads.
_RESERVED_PREDICATES = {"comention", "rel", "chained", "bridged"}

_RULE_HEAD_RE = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*\(\s*([^)]+)\s*\)\s*:-")


def _atom(value: str) -> str:
    """Normalize a value into a lowercase datalog constant."""
    atom = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return atom or "unknown"


class Enricher:
    """Derives inferences, suggestions, conflicts, and insights from a graph
    produced by graphier.graph.build_graph."""

    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.names: dict[str, str] = {}  # datalog atom -> display text
        for node in graph["nodes"]:
            self.names.setdefault(_atom(node["text"]), node["text"])
        for note_id, title in graph["note_titles"].items():
            self.names.setdefault(_atom(note_id), title)

    # ---- inferred connections ----

    def inferred_connections(self, limit: int = 20) -> list[dict[str, Any]]:
        reasoner = DatalogReasoner()
        comentions: set[tuple[str, str, str]] = set()
        pairs_in_same_note: set[frozenset] = set()

        # Dates bridge everything and mean nothing; notes aren't mentions.
        entity_nodes = [n for n in self.graph["nodes"] if n["label"] not in ("NOTE", "DATE")]
        by_note: dict[str, list[str]] = defaultdict(list)
        for node in entity_nodes:
            for note in node["notes"]:
                by_note[note].append(_atom(node["text"]))

        for note, atoms in by_note.items():
            for i, a in enumerate(atoms):
                for b in atoms[i + 1 :]:
                    if a == b:
                        continue
                    pairs_in_same_note.add(frozenset((a, b)))
                    comentions.add((a, b, _atom(note)))
                    comentions.add((b, a, _atom(note)))

        for a, b, note in comentions:
            reasoner.add_fact(f"comention({a}, {b}, {note})")

        for edge in self.graph["edges"]:
            if edge["origin"] != "extracted" or edge["predicate"] in _GENERIC_PREDICATES:
                continue
            src = _atom(edge["source"].split(":", 1)[1])
            dst = _atom(edge["target"].split(":", 1)[1])
            reasoner.add_fact(f"rel({src}, {dst}, {_atom(edge['predicate'])})")

        for rule, _, _ in INFERENCE_RULES:
            reasoner.add_rule(rule)

        # Rules the user wrote in ```datalog blocks program the same reasoner.
        custom_heads: list[tuple[str, int, dict[str, str]]] = []
        for entry in self.graph.get("custom_rules", []):
            head = _RULE_HEAD_RE.match(entry["rule"])
            if not head or head.group(1) in _RESERVED_PREDICATES:
                continue
            arity = len(head.group(2).split(","))
            try:
                reasoner.add_rule(entry["rule"])
            except Exception:
                continue  # a malformed rule silently contributes nothing
            custom_heads.append((head.group(1), arity, entry))

        reasoner.derive_all()

        results: list[dict[str, Any]] = []
        seen: set[frozenset] = set()

        for predicate, arity, entry in custom_heads:
            variables = [f"V{i}" for i in range(arity)]
            pattern = f"{predicate}({', '.join(variables)})"
            for binding in reasoner.query(pattern):
                values = [binding[v] for v in variables]
                key = frozenset([predicate, *values])
                if key in seen or len(set(values)) < min(2, arity):
                    continue
                seen.add(key)
                results.append(
                    {
                        "kind": "custom",
                        "source": self.names.get(values[0], values[0]),
                        "target": self.names.get(values[1], values[1]) if arity > 1 else "",
                        "because": (
                            f"{predicate.replace('_', ' ')} — your rule in "
                            f"{self.graph['note_titles'].get(entry['note'], entry['note'])}: "
                            f"{entry['rule']}"
                        ),
                    }
                )

        for binding in reasoner.query("chained(X, Z, Y, P1, P2)"):
            x, z = binding["X"], binding["Z"]
            key = frozenset((x, z))
            if x == z or key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "kind": "chained",
                    "source": self.names.get(x, x),
                    "target": self.names.get(z, z),
                    "because": (
                        f"{self.names.get(x, x)} {binding['P1'].replace('_', ' ')} "
                        f"{self.names.get(binding['Y'], binding['Y'])}, which "
                        f"{binding['P2'].replace('_', ' ')} {self.names.get(z, z)}"
                    ),
                }
            )

        for binding in reasoner.query("bridged(X, Y, B, N1, N2)"):
            x, y, bridge = binding["X"], binding["Y"], binding["B"]
            key = frozenset((x, y))
            if (
                x == y
                or key in seen
                or key in pairs_in_same_note  # only *hidden* connections
                or binding["N1"] == binding["N2"]
            ):
                continue
            seen.add(key)
            results.append(
                {
                    "kind": "bridged",
                    "source": self.names.get(x, x),
                    "target": self.names.get(y, y),
                    "because": (
                        f"never appear together, but both appear with "
                        f"{self.names.get(bridge, bridge)} "
                        f"({self.names.get(binding['N1'], binding['N1'])} / "
                        f"{self.names.get(binding['N2'], binding['N2'])})"
                    ),
                }
            )

        return results[:limit]

    # ---- link suggestions ----

    def suggestions_for(self, note_id: str) -> list[dict[str, Any]]:
        already_linked = {
            edge["target"]
            for edge in self.graph["edges"]
            if edge["origin"] == "manual" and note_id in edge["notes"]
        }
        suggestions = []
        for node in self.graph["nodes"]:
            if node["label"] in ("NOTE", "DATE") or note_id not in node["notes"]:
                continue
            others = [n for n in node["notes"] if n != note_id]
            if not others or node["id"] in already_linked:
                continue
            suggestions.append(
                {
                    "text": node["text"],
                    "label": node["label"],
                    "also_in": [
                        {"id": n, "title": self.graph["note_titles"].get(n, n)} for n in others
                    ],
                }
            )
        suggestions.sort(key=lambda s: len(s["also_in"]), reverse=True)
        return suggestions

    # ---- conflicts ----

    def conflicts(self) -> list[dict[str, Any]]:
        claims: dict[tuple[str, str], dict[str, set]] = defaultdict(lambda: defaultdict(set))
        for edge in self.graph["edges"]:
            if edge["origin"] != "extracted" or edge["predicate"] in _GENERIC_PREDICATES:
                continue
            key = (edge["source"], edge["predicate"])
            claims[key][edge["target"]].update(edge["notes"])

        found = []
        for (source, predicate), objects in claims.items():
            if len(objects) < 2:
                continue
            found.append(
                {
                    "subject": self._display(source),
                    "predicate": predicate.replace("_", " "),
                    "claims": [
                        {
                            "object": self._display(target),
                            "notes": [
                                {"id": n, "title": self.graph["note_titles"].get(n, n)}
                                for n in sorted(notes)
                            ],
                        }
                        for target, notes in objects.items()
                    ],
                }
            )
        return found

    # ---- insights ----

    def insights(self, top: int = 6) -> list[dict[str, Any]]:
        g = nx.Graph()
        for node in self.graph["nodes"]:
            if node["label"] not in ("NOTE", "DATE"):
                g.add_node(node["id"], text=node["text"], label=node["label"])
        for edge in self.graph["edges"]:
            if g.has_node(edge["source"]) and g.has_node(edge["target"]):
                g.add_edge(edge["source"], edge["target"])
        # Co-mention edges so centrality reflects shared context, not only
        # extracted relations.
        by_note: dict[str, list[str]] = defaultdict(list)
        for node in self.graph["nodes"]:
            if node["label"] in ("NOTE", "DATE"):
                continue
            for note in node["notes"]:
                by_note[note].append(node["id"])
        for members in by_note.values():
            for i, a in enumerate(members):
                for b in members[i + 1 :]:
                    g.add_edge(a, b)

        if g.number_of_nodes() == 0:
            return []
        scores = CentralityCalculator().calculate_pagerank(g)["centrality"]
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top]
        return [
            {
                "text": self._display(node_id),
                "label": node_id.split(":", 1)[0],
                "score": round(score, 4),
            }
            for node_id, score in ranked
        ]

    def _display(self, node_id: str) -> str:
        for node in self.graph["nodes"]:
            if node["id"] == node_id:
                return node["text"]
        return node_id


def enrich(graph: dict[str, Any]) -> dict[str, Any]:
    enricher = Enricher(graph)
    return {
        "inferred": enricher.inferred_connections(),
        "conflicts": enricher.conflicts(),
        "insights": enricher.insights(),
    }
