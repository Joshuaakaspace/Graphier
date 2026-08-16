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


DARK_LABEL_COLORS = {
    "PERSON": "#e08a51",
    "ORG": "#a37fe0",
    "GPE": "#6cbf71",
    "DATE": "#64a3e8",
    "CONCEPT": "#b8a02e",
    "NOTE": "#5fb3a3",
}


def _mix(c1: str, c2: str, t: float) -> str:
    """Blend two hex colors: t=0 → c1, t=1 → c2."""
    a = [int(c1[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


from dataclasses import dataclass, field  # noqa: E402


@dataclass
class PlotStyle:
    """Visual style for the library plots.

    Use a preset — `PlotStyle.paper()` (default) or `PlotStyle.dark()` —
    or construct your own; `colors` overrides individual entity-type hues
    on top of the preset's palette.

        style = graphier.PlotStyle.dark()
        style = graphier.PlotStyle(background="#101418", ink="#eaeaea",
                                   colors={"PERSON": "#ffb86b"})
    """

    background: str = "#fbfaf8"
    ink: str = "#232725"
    ink_soft: str = "#6b716e"
    line: str = "#c9c5bd"
    grid: str = "#e7e3db"
    node_ring: str = "#ffffff"
    colors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def paper(cls) -> "PlotStyle":
        return cls()

    @classmethod
    def dark(cls) -> "PlotStyle":
        return cls(
            background="#191c1b", ink="#e4e6e4", ink_soft="#969e9a",
            line="#3a403d", grid="#2a2f2d", node_ring="#191c1b",
            colors=dict(DARK_LABEL_COLORS),
        )

    def color_of(self, label: str) -> str:
        if label in self.colors:
            return self.colors[label]
        return label_color(label)

    def faded(self, color: str, amount: float = 0.82) -> str:
        return _mix(color, self.background, amount)


def _resolve_style(style) -> PlotStyle:
    if style is None or style == "paper":
        return PlotStyle.paper()
    if style == "dark":
        return PlotStyle.dark()
    if isinstance(style, PlotStyle):
        return style
    raise ValueError(f"unknown style {style!r} — use 'paper', 'dark', or a PlotStyle")


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
        include_related: bool = False,
        style=None,
        focus: str | None = None,
    ):
        """Draw the knowledge graph. Returns the matplotlib Axes.

        style: "paper" (default), "dark", or a graphier.PlotStyle.
        focus: an entity name — that node and its neighborhood stay vivid
        (with a soft glow on the focus node) while the rest fades, like
        the app's hover effect.

        Defaults are opinionated for legibility: UNKNOWN and DATE nodes and
        generic co-occurrence ("related_to") edges are excluded from the
        drawing — the data keeps them; pass exclude_labels=("UNKNOWN",) /
        include_related=True to draw everything.
        """
        plt = self._plt()
        import matplotlib.patheffects as pe
        import networkx as nx

        st = _resolve_style(style)
        g = self.to_networkx(exclude_labels=exclude_labels)
        if not include_related:
            g.remove_edges_from(
                [(u, v) for u, v, d in g.edges(data=True) if d["predicate"] == "related_to"]
            )

        vivid: set[str] | None = None
        if focus is not None:
            wanted = focus.strip().lower()
            node = next((n for n in g if n.strip().lower() == wanted), None)
            if node is None:
                raise ValueError(f"focus entity not in graph: {focus!r}")
            vivid = {node} | set(g.predecessors(node)) | set(g.successors(node))

        if ax is None:
            _, ax = plt.subplots(figsize=(11, 8))
        fig = ax.figure
        fig.set_facecolor(st.background)
        ax.set_facecolor(st.background)

        try:
            pos = nx.kamada_kawai_layout(g.to_undirected())
        except Exception:  # disconnected corner cases fall back to spring
            pos = nx.spring_layout(g, seed=seed, k=3.0 / max(1, len(g)) ** 0.5, iterations=200)

        halo = [pe.withStroke(linewidth=3, foreground=st.background)]

        def is_vivid(n: str) -> bool:
            return vivid is None or n in vivid

        edge_cols = [
            st.line if (is_vivid(u) and is_vivid(v)) else st.faded(st.line)
            for u, v in g.edges()
        ]
        nx.draw_networkx_edges(
            g, pos, ax=ax, edge_color=edge_cols, width=1.3, alpha=0.95,
            arrows=True, arrowsize=13, arrowstyle="-|>",
            connectionstyle="arc3,rad=0.08", node_size=520,
        )

        nodes = list(g)
        colors = [
            st.color_of(g.nodes[n]["label"]) if is_vivid(n)
            else st.faded(st.color_of(g.nodes[n]["label"]))
            for n in nodes
        ]
        sizes = [260 + 90 * g.degree(n) for n in nodes]
        if vivid is not None:
            # a soft glow behind the focus node
            fnode = next(n for n in vivid if n.strip().lower() == focus.strip().lower())
            fi = nodes.index(fnode)
            ax.scatter(*pos[fnode], s=sizes[fi] * 3.2, color=colors[fi],
                       alpha=0.18, zorder=1, linewidths=0)
            ax.scatter(*pos[fnode], s=sizes[fi] * 1.9, color=colors[fi],
                       alpha=0.25, zorder=1, linewidths=0)
        nx.draw_networkx_nodes(
            g, pos, ax=ax, node_color=colors, node_size=sizes,
            edgecolors=st.node_ring, linewidths=2.0,
        )

        # Labels sit below their node with a halo, never on top of it, and
        # get greedily nudged apart when two would collide.
        placed: list[tuple[float, float]] = []
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        span_x = (max(xs) - min(xs)) or 1.0
        span_y = (max(ys) - min(ys)) or 1.0
        for node in sorted(g, key=lambda n: -g.degree(n)):
            x, y = pos[node]
            ly = y - 0.045 * span_y - (sizes[nodes.index(node)] ** 0.5) * 0.0016 * span_y
            for px, py in placed:
                if abs(x - px) < 0.14 * span_x and abs(ly - py) < 0.045 * span_y:
                    ly = py - 0.05 * span_y
            placed.append((x, ly))
            ax.text(
                x, ly, node, ha="center", va="top", fontsize=9.5,
                color=st.ink if is_vivid(node) else st.faded(st.ink, 0.6),
                path_effects=halo, zorder=6,
            )

        if edge_labels:
            labels = {
                (u, v): d["predicate"].replace("_", " ")
                for u, v, d in g.edges(data=True)
                if d["predicate"] != "related_to" and is_vivid(u) and is_vivid(v)
            }
            texts = nx.draw_networkx_edge_labels(
                g, pos, ax=ax, edge_labels=labels, font_size=7.5,
                font_color=st.ink_soft, rotate=False,
                bbox={"boxstyle": "round,pad=0.15", "fc": st.background, "ec": "none", "alpha": 0.9},
            )
            for t in texts.values():
                t.set_fontstyle("italic")

        present = sorted({g.nodes[n]["label"] for n in g})
        handles = [
            plt.Line2D([], [], marker="o", linestyle="", color=st.color_of(l),
                       markeredgecolor=st.node_ring, markeredgewidth=1.2,
                       label=l.title(), markersize=9)
            for l in present
        ]
        ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=8.5,
                  labelcolor=st.ink_soft, handletextpad=0.4, borderaxespad=0.2)
        ax.set_axis_off()
        ax.margins(0.10)
        title = "Knowledge graph" if focus is None else f"Knowledge graph · {focus}"
        ax.set_title(title, fontsize=13, color=st.ink, loc="left",
                     fontweight="bold", pad=12)
        return ax

    def plot_timeline(
        self,
        ax=None,
        max_rows: int = 8,
        style=None,
        highlight: str | list[str] | None = None,
    ):
        """Draw entity lifelines over time. Returns the matplotlib Axes.

        style: "paper" (default), "dark", or a graphier.PlotStyle.
        highlight: entity name(s) — those lifelines stay vivid and grow
        slightly; the rest fade back.
        """
        plt = self._plt()
        import matplotlib.patheffects as pe

        st = _resolve_style(style)
        events = self.timeline()
        if not events:
            raise ValueError("no dated events in this vault yet")

        wanted = None
        if highlight is not None:
            names = [highlight] if isinstance(highlight, str) else list(highlight)
            wanted = {n.strip().lower() for n in names}

        def t_of(e):
            y, m, d = e["sort_key"]
            return y + (m - 1) / 12 if m else y + 0.5

        rows: dict[tuple[str, str], list[float]] = {}
        for e in events:
            for ent in e["entities"]:
                rows.setdefault((ent["text"], ent["label"]), []).append(t_of(e))
        top = sorted(rows.items(), key=lambda kv: -len(kv[1]))[:max_rows]
        top.sort(key=lambda kv: kv[1][0])

        if ax is None:
            _, ax = plt.subplots(figsize=(10, 0.62 * len(top) + 1.4))
        fig = ax.figure
        fig.set_facecolor(st.background)
        ax.set_facecolor(st.background)

        all_t = [t for _, ts in top for t in ts]
        pad = max(1.5, (max(all_t) - min(all_t)) * 0.04)
        x_hi = max(all_t) + pad

        halo = [pe.withStroke(linewidth=3, foreground=st.background)]
        for i, ((text, label), ts) in enumerate(top):
            hot = wanted is None or text.strip().lower() in wanted
            color = st.color_of(label) if hot else st.faded(st.color_of(label), 0.75)
            size, lw = (72, 3.2) if (wanted is not None and hot) else (58, 2.5)
            if len(ts) > 1:
                ax.hlines(i, min(ts), max(ts), color=color,
                          alpha=0.45 if (wanted is not None and hot) else 0.30,
                          linewidth=lw, capstyle="round")
            ax.scatter(ts, [i] * len(ts), color=color, s=size, zorder=3,
                       edgecolors=st.background, linewidths=1.4)
            years = sorted({int(t) for t in ts})
            span = str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
            ax.annotate(span, (max(ts), i), xytext=(9, 0),
                        textcoords="offset points", va="center", fontsize=7.5,
                        color=st.ink_soft if hot else st.faded(st.ink_soft, 0.5),
                        path_effects=halo)

        ax.set_yticks(range(len(top)))
        labels_ = ax.set_yticklabels([text for (text, _), _ in top], fontsize=9.5)
        for lab, ((text, _), _) in zip(labels_, top):
            hot = wanted is None or text.strip().lower() in wanted
            lab.set_color(st.ink if hot else st.faded(st.ink, 0.55))
            if wanted is not None and hot:
                lab.set_fontweight("bold")
        ax.invert_yaxis()
        ax.set_xlim(min(all_t) - pad, x_hi + pad)
        ax.grid(axis="x", color=st.grid, linewidth=0.9)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", colors=st.ink_soft, labelsize=8.5, length=0)
        ax.tick_params(axis="y", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title("Entity lifelines", fontsize=13, color=st.ink, loc="left",
                     fontweight="bold", pad=12)
        return ax


def open(vault_dir: str | Path) -> VaultSession:  # noqa: A001 - deliberate, matplotlib-style
    """Open a vault for reading: `v = graphier.open("~/notes")`."""
    return VaultSession(vault_dir)
