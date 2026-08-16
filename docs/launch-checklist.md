# Launch checklist

The repo side is done (LICENSE, CI, Docker, demo mode, hero GIF,
CONTRIBUTING, ROADMAP, templates). What remains needs the repo owner.

## Repo settings (5 minutes)

- [ ] Topics: `knowledge-graph`, `pkm`, `note-taking`, `local-first`,
      `obsidian-alternative`, `datalog`, `knowledge-management`
- [ ] Description: *"Obsidian-like notes where the knowledge graph builds
      itself — no LLM, no cloud, every claim quotes its source sentence"*
- [ ] Social preview image: upload `docs/graph-view.png`
- [ ] Enable **Discussions**
- [ ] Tag `v0.1.0` (the release workflow builds and attaches the wheel)
- [ ] PyPI (optional but recommended): create a pypi.org account →
      Publishing → add a *pending publisher* for `Joshuaakaspace/Graphier`,
      workflow `release.yml`, environment `pypi` → set the GitHub repo
      **variable** `PYPI_PUBLISH=true` → re-tag or re-run the release
      workflow. No token/secret needed (trusted publishing). After that,
      `pip install graphier` works for everyone.

## Seed issues (copy, adjust, post — label the first four `good first issue`)

1. **Add EPUB support to document ingestion** — `documents.py` dispatches
   extractors by extension; an EPUB is a zip of XHTML, so `zipfile` + the
   existing `_HTMLTextExtractor` covers it. ~20 lines + a test with a
   hand-built fixture (see `make_docx` in `tests/test_pdf.py` for the
   pattern).
2. **Parse "March 3, 1948" style dates** — `timeline.py` handles ISO,
   "March 1948", d/m/y, and bare years; month-name-with-day is missing.
   One regex + a test in `tests/test_timeline.py`.
3. **Dark-mode pass on the lifeline chart** — the chart reads CSS tokens
   but hasn't been visually tuned against the dark palette; check dot
   stroke and gridline contrast.
4. **Entity page: co-occurring entities section** — "often appears with"
   using the co-mention data already in the graph dict; backend field +
   one panel section.
5. **Conflict resolution workflow** — accept / mark-superseded on
   conflicts, writing the verdict back as a fact with provenance
   (design discussion first).
6. **Vault diff between snapshots** — `graph_at()` exists for two shas;
   diff nodes/edges and render what appeared/vanished/changed.
7. **Obsidian vault import** — handle frontmatter and `#tags` when
   pointing GRAPHIER_VAULT at an existing Obsidian folder.
8. **MCP server** — expose search/entity/relations/Datalog/provenance to
   MCP clients (roadmap headliner; design discussion first).

## Launch posts

- **Show HN** — *"Show HN: An Obsidian-like app where the knowledge graph
  builds itself (no LLM)"*. Weekday morning US time; stay in the thread
  all day. Lead comment: why deterministic + provenance, the lean-install
  trick, what's deliberately not in scope.
- **r/ObsidianMD, r/PKMS, r/selfhosted** — frame as an experiment, show
  the GIF, invite domain-block ideas.
- **Semantica community** — ask for a showcase mention; Graphier is a
  downstream demo of their engine components.
