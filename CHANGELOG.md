# Changelog

## Unreleased

- Library API: `import graphier; v = graphier.open("~/notes")` — entities,
  relations, Datalog queries, conflicts, timeline, `to_networkx()`, and
  matplotlib plotting (`plot_graph()`, `plot_timeline()`) via the
  `graphier[viz]` extra. Same determinism, same sentence-level evidence.
  Plots take styles and effects: "paper"/"dark" presets or a custom
  `PlotStyle`, `focus=` neighborhood spotlight with glow on the graph,
  `highlight=` lifeline spotlight on the timeline.

- Lean PyPI install: `pip install graphier` no longer drags in
  multi-gigabyte ML dependencies; `graphier setup` fetches the extraction
  engine with `--no-deps`, and a friendly message explains the one
  command if it's missing. Release workflow gains PyPI trusted
  publishing (no token needed).

- **MCP server** (`graphier-mcp`): the vault's knowledge graph queryable
  by Claude Code, Claude Desktop, Cursor, and any MCP client over stdio —
  nine tools (search, entity dossiers, relations, Datalog, conflicts,
  timeline, notes), every answer carrying sentence-level provenance.
- Community infrastructure: CONTRIBUTING, extension guide, roadmap,
  issue/PR templates, packaging + release workflow.

## 0.1.0 — first public cut

Everything so far, in merge order:

- **Phase 1 walking skeleton** (#1): Markdown vault, FastAPI backend,
  CodeMirror editor with live entity underlines, entity/relations panel.
- **Vault intelligence + provenance** (#2): Datalog inference with
  derivations, conflict detection, link suggestions, PageRank insights;
  Sigma.js graph canvas; user-programmable ```datalog rules;
  sentence-level evidence, entity pages, one-click linking.
- **Search, time travel, domains, live queries** (#3): TF-IDF +
  graph-boosted search; git-backed snapshots with graph replay;
  vault-defined entity types and `{TYPE} verb {TYPE}` relation templates;
  ```query blocks with Datalog support.
- **Document sources** (#4): PDF, HTML, DOCX, TXT ingestion through the
  same pipeline, read-only, with sentence evidence into each document.
- **Graph visuals + chronology** (#5): edge labels, arrows, hover focus,
  legend filters, inferred-edge overlay; cross-source timeline.
- **Entity lifeline chart** (#6): the chronology, graphically; palette
  colorblind-safety fix.
- **README repositioning** (#7, #8): Graphier-first framing, consolidated
  Semantica credit, illustrated chronology section.
- **Launch kit** (#9, #10): MIT LICENSE, demo mode, multi-stage
  Dockerfile, GitHub Actions CI, hero GIF.
