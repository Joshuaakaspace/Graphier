"""Graphier as a library: the vault's knowledge in a script or notebook.

    import graphier

    v = graphier.open("~/notes")
    v.entities("PERSON")            # rows, plain dicts
    v.query("?- empire_builder(P, B)")
    v.to_networkx()                 # hand the graph to any tool you like

    v.plot_graph()                  # matplotlib: the knowledge graph
    v.plot_timeline()               # matplotlib: entity lifelines over time

Plotting needs matplotlib (`pip install graphier[viz]`); everything else
is dependency-free beyond Graphier itself. Same determinism, same
provenance: every row that asserts something carries its evidence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")

from .enrichment import Enricher, enrich  # noqa: E402
from .extraction import ExtractionService  # noqa: E402
from .graph import build_graph, entity_page  # noqa: E402
from .search import search as _search  # noqa: E402
from .timeline import build_timeline  # noqa: E402
from .vault import Vault  # noqa: E402

# Mirrors the app's light-theme palette (frontend/src/index.css).
LABEL_COLORS = {
    "PERSON": "#b3541e",
    "ORG": "#6e40c9",
    "GPE": "#2e7d32",
    "DATE": "#1565c0",
    "CONCEPT": "#8a7500",
    "NOTE": "#1f6f61",
}
_CUSTOM_PALETTE = ["#c2185b", "#00838f", "#7cb342", "#5e35b1", "#ef6c00", "#7d6608"]


def label_color(label: str) -> str:
    if label in LABEL_COLORS:
        return LABEL_COLORS[label]
    return _CUSTOM_PALETTE[sum(ord(c) for c in label) % len(_CUSTOM_PALETTE)]


class VaultSession:
    """A read view over one vault. Cheap to keep around: extraction is
    cached by content hash, so repeated calls only re-read changed notes."""

    def __init__(self, vault_dir: str | Path):
        self.vault = Vault(Path(vault_dir).expanduser())
        self._extractor = ExtractionService()

    # ---- data access ----

    def graph(self) -> dict[str, Any]:
        return build_graph(self.vault, self._extractor)

    def entities(self, label: str | None = None) -> list[dict[str, Any]]:
        return [
            n for n in self.graph()["nodes"]
            if n["label"] != "NOTE" and (label is None or n["label"] == label.upper())
        ]

    def relations(self, predicate: str | None = None) -> list[dict[str, Any]]:
        graph = self.graph()
        display = {n["id"]: n["text"] for n in graph["nodes"]}
        wanted = predicate.lower().replace(" ", "_") if predicate else None
        return [
            {**e, "subject": display.get(e["source"]), "object": display.get(e["target"])}
            for e in graph["edges"]
            if wanted is None or e["predicate"] == wanted
        ]

    def entity(self, name: str) -> dict[str, Any] | None:
        graph = self.graph()
        wanted = name.strip().lower()
        node = next((n for n in graph["nodes"] if n["text"].strip().lower() == wanted), None)
        return entity_page(graph, node["id"]) if node else None

    def search(self, query: str) -> dict[str, Any]:
        notes = {m.id: self.vault.read(m.id) for m in self.vault.list_notes()}
        graph = self.graph()
        return _search(query, notes, graph["note_titles"], graph)

    def query(self, pattern: str) -> list[dict[str, str]]:
        pattern = pattern.strip()
        if pattern.startswith("?-"):
            pattern = pattern[2:].strip()
        return Enricher(self.graph()).datalog_query(pattern)

    def conflicts(self) -> list[dict[str, Any]]:
        return enrich(self.graph())["conflicts"]

    def inferred(self) -> list[dict[str, Any]]:
        return enrich(self.graph())["inferred"]

    def timeline(self) -> list[dict[str, Any]]:
        return build_timeline(self.vault, self._extractor)

    def to_networkx(
        self,
        include_notes: bool = False,
        exclude_labels: tuple[str, ...] = ("UNKNOWN",),
    ):
        """The knowledge graph as a networkx.DiGraph, ready for any tool.

        UNKNOWN-type nodes (low-confidence extraction noise) are excluded
        by default; pass exclude_labels=() to keep everything.
        """
        import networkx as nx

        graph = self.graph()
        g = nx.DiGraph()
        for node in graph["nodes"]:
            if not include_notes and node["label"] == "NOTE":
                continue
            if node["label"] in exclude_labels:
                continue
            g.add_node(node["text"], label=node["label"], mentions=node["count"])
        for edge in graph["edges"]:
            display = {n["id"]: n["text"] for n in graph["nodes"]}
            src, dst = display.get(edge["source"]), display.get(edge["target"])
            if g.has_node(src) and g.has_node(dst):
                g.add_edge(src, dst, predicate=edge["predicate"], origin=edge["origin"],
                           evidence=edge["evidence"])
        return g

    # ---- plotting (matplotlib, optional) ----

    @staticmethod
    def _plt():
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise ImportError(
                "plotting needs matplotlib — install with: pip install graphier[viz]"
            ) from exc
        return plt

    def plot_graph(
        self,
        ax=None,
        edge_labels: bool = True,
        seed: int = 7,
        exclude_labels: tuple[str, ...] = ("UNKNOWN", "DATE"),
    ):
        """Draw the knowledge graph. Returns the matplotlib Axes.

        DATE nodes are excluded from the drawing by default (they connect
        to everything and add clutter, and the timeline plot covers time);
        pass exclude_labels=("UNKNOWN",) to include them.
        """
        plt = self._plt()
        import networkx as nx

        g = self.to_networkx(exclude_labels=exclude_labels)
        if ax is None:
            _, ax = plt.subplots(figsize=(11, 8))
        try:
            pos = nx.kamada_kawai_layout(g.to_undirected())
        except Exception:  # disconnected corner cases fall back to spring
            pos = nx.spring_layout(g, seed=seed, k=3.0 / max(1, len(g)) ** 0.5, iterations=200)
        colors = [label_color(g.nodes[n]["label"]) for n in g]
        sizes = [180 + 80 * g.degree(n) for n in g]
        nx.draw_networkx_edges(g, pos, ax=ax, edge_color="#c9c9c9", width=1.2,
                               arrows=True, arrowsize=11)
        nx.draw_networkx_nodes(g, pos, ax=ax, node_color=colors, node_size=sizes,
                               edgecolors="white", linewidths=1.4)
        nx.draw_networkx_labels(g, pos, ax=ax, font_size=9)
        if edge_labels:
            labels = {(u, v): d["predicate"].replace("_", " ")
                      for u, v, d in g.edges(data=True) if d["predicate"] != "related_to"}
            nx.draw_networkx_edge_labels(g, pos, ax=ax, edge_labels=labels,
                                         font_size=7, font_color="#666666")
        present = sorted({g.nodes[n]["label"] for n in g})
        handles = [plt.Line2D([], [], marker="o", linestyle="", color=label_color(l),
                              label=l, markersize=8) for l in present]
        ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8)
        ax.set_axis_off()
        ax.set_title("Knowledge graph", fontsize=11)
        return ax

    def plot_timeline(self, ax=None, max_rows: int = 8):
        """Draw entity lifelines over time. Returns the matplotlib Axes."""
        plt = self._plt()

        events = self.timeline()
        if not events:
            raise ValueError("no dated events in this vault yet")

        def t_of(e):
            y, m, d = e["sort_key"]
            return y + (m - 1) / 12 if m else y + 0.5

        rows: dict[tuple[str, str], list[tuple[float, str]]] = {}
        for e in events:
            for ent in e["entities"]:
                rows.setdefault((ent["text"], ent["label"]), []).append(
                    (t_of(e), e["sentence"])
                )
        top = sorted(rows.items(), key=lambda kv: -len(kv[1]))[:max_rows]
        top.sort(key=lambda kv: kv[1][0][0])

        if ax is None:
            _, ax = plt.subplots(figsize=(10, 0.6 * len(top) + 1.2))
        for i, ((text, label), points) in enumerate(top):
            xs = [p[0] for p in points]
            color = label_color(label)
            if len(xs) > 1:
                ax.hlines(i, min(xs), max(xs), color=color, alpha=0.35, linewidth=2)
            ax.scatter(xs, [i] * len(xs), color=color, s=55, zorder=3,
                       edgecolors="white", linewidths=1.2)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels([text for (text, _), _ in top], fontsize=9)
        ax.invert_yaxis()
        ax.grid(axis="x", color="#e3e0da", linewidth=0.8)
        ax.set_axisbelow(True)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.set_title("Entity lifelines", fontsize=11)
        return ax


def open(vault_dir: str | Path) -> VaultSession:  # noqa: A001 - deliberate, matplotlib-style
    """Open a vault for reading: `v = graphier.open("~/notes")`."""
    return VaultSession(vault_dir)
