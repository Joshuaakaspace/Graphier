# Roadmap

The phases come from [ARCHITECTURE.md](ARCHITECTURE.md); this is the live
status. Contributions welcome on anything unchecked — open an issue first
for the bigger ones so we can agree on shape.

## Done

- [x] Vault + editor with live entity underlines (Phase 1)
- [x] Vault intelligence: Datalog inference, conflict detection, link
      suggestions, PageRank central entities
- [x] Graph canvas: force layout, edge labels, hover focus, legend filters,
      inferred-edge overlay
- [x] User-programmable rules (```datalog blocks)
- [x] Sentence-level provenance + entity pages + one-click linking
- [x] Hybrid search (TF-IDF + graph boost)
- [x] Time travel (git snapshots, graph-at-commit replay)
- [x] Domains: vault-defined entity types + typed relation templates
- [x] Live query notes (```query blocks, Datalog queries)
- [x] Document sources: PDF, HTML, DOCX, TXT
- [x] Chronology: cross-source timeline + entity lifeline chart
- [x] Launch kit: LICENSE, demo mode, Docker, CI
- [x] MCP server — the vault graph queryable by Claude/Cursor/any MCP
      client, provenance included

## Next
- [ ] **Conflict resolution workflow** — accept / mark-superseded buttons on
      conflicts, writing the verdict back as a fact with provenance.
- [ ] **Vault diff** — "what changed between snapshot A and B": entities
      appeared/vanished, claims changed.
- [ ] **OCR for scanned PDFs** — optional tesseract path in documents.py.
- [ ] **Obsidian vault import** — point Graphier at an existing vault
      folder; frontmatter + tag handling.
- [ ] **More document formats** — EPUB, CSV/XLSX (row-level treatment).
- [ ] **Date parsing depth** — "March 3, 1948", relative dates, ranges.
- [ ] **Semantic search** — optional embeddings backend for fuzzy recall
      (must stay optional; the deterministic path is the default).
- [ ] **Desktop packaging** — Tauri/Electron wrapper.

## Non-goals

- A required LLM anywhere in the extraction → graph path.
- A cloud service. Graphier is local-first; your files are the database.
