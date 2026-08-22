# Launch checklist

The repo side is done (LICENSE, CI, Docker, demo mode, hero GIF,
CONTRIBUTING, ROADMAP, templates). What remains needs the repo owner.

## Repo settings (5 minutes)

On https://github.com/ioteverythin/Graphier, click the **gear** next to
"About" (top of the right sidebar) and paste — this cannot be set from a
PR, only the owner's UI/API:

- [ ] Description:

      ```
      Obsidian-like notes where the knowledge graph builds itself — no LLM, no cloud, every claim quotes its source sentence.
      ```

- [ ] Topics (comma/Enter separated):

      ```
      knowledge-graph, note-taking, pkm, obsidian, markdown, local-first, datalog, entity-extraction, mcp-server, self-hosted, fastapi, react, provenance, python
      ```

- [ ] Social preview image: upload `docs/graph-view.png`
- [ ] Enable **Discussions**
- [ ] Tag `v0.1.0` (the release workflow builds and attaches the wheel)
- [x] PyPI pending publisher configured (`ioteverythin/Graphier`,
      workflow `release.yml`, environment "(Any)")
- [ ] Set the GitHub repo **variable** `PYPI_PUBLISH=true`
      (Settings → Secrets and variables → Actions → Variables) —
      verify it survived the repo transfer
- [ ] Create the `pypi` environment (Settings → Environments) — the
      workflow declares it; with the publisher set to "(Any)" it just
      needs to exist

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
8. **Fuzzy / typo-tolerant search** — BM25 is exact-match; a cheap
   edit-distance fallback for zero-hit queries would soften typos
   (`search.py`, see docs/how-search-works.md for the constraints).

## Launch posts

- **Show HN** — *"Show HN: An Obsidian-like app where the knowledge graph
  builds itself (no LLM)"*. Weekday morning US time; stay in the thread
  all day. Lead comment: why deterministic + provenance, the lean-install
  trick, what's deliberately not in scope.
- **r/ObsidianMD, r/PKMS, r/selfhosted** — frame as an experiment, show
  the GIF, invite domain-block ideas.
- **Semantica community** — ask for a showcase mention; Graphier is a
  downstream demo of their engine components.
