# Graphier

**An Obsidian-like knowledge workspace where the graph builds itself — no
LLM, no cloud, and every claim can quote the sentence it came from.**

[![CI](https://github.com/ioteverythin/Graphier/actions/workflows/ci.yml/badge.svg)](https://github.com/ioteverythin/Graphier/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg)](https://www.python.org/)

![Graphier demo](docs/demo.gif)

You write plain Markdown notes (or drop in PDFs, Word documents, and web
pages); a deterministic extraction pipeline turns them into a typed
knowledge graph underneath — people, organizations, places, dates, and
your own domain types light up as you type, relations are extracted with
confidence scores, and `[[wiki-links]]` become explicit edges. No LLM, no
cloud: everything is derived from your files, every claim can quote the
sentence it came from, and the whole graph rebuilds from the vault at any
time. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

**Status: Phase 1 + vault intelligence** — vault CRUD, live entity extraction
with in-editor underlines, entity/relations panel, vault-wide graph
aggregation, and a deterministic enrichment layer:

- **Inferred connections** — a Datalog reasoner forward-chains rules over
  extracted facts: multi-hop chains ("Widget Inc ↔ Ada Lovelace, because
  Widget Inc was acquired by Acme Corp, which was founded by Ada Lovelace")
  and hidden bridges ("X and Y never appear together, but both appear with
  Z"). Every inference carries its derivation.
- **Conflict detection** — the same subject + predicate asserted differently
  in different notes gets flagged with both sources ("Acme Corp founded by:
  Grace Hopper (History) vs Ada Lovelace (Research Log)").
- **Link suggestions** — entities in the current note that other notes also
  mention.
- **Central entities** — PageRank over the vault graph: what your vault
  actually revolves around.
- **Graph canvas** — a force-directed Sigma.js view of the whole vault, nodes
  colored by type and sized by mentions. Click a node or edge for its
  provenance (which notes it came from, extraction confidence, manual vs
  extracted); double-click a node to jump to its note.
- **Entity pages with sentence-level provenance** — click any entity name to
  see everything the vault knows about it: every mention quoted verbatim with
  its source note, every relation backed by the exact sentence that asserted
  it, plus the conflicts and inferences it participates in.
- **One-click linking** — accept a link suggestion and the `[[wiki-link]]` is
  written into your Markdown for you.
- **Hybrid search** — TF-IDF ranking over note bodies, graph-boosted: a note
  that *mentions the entity you searched for* outranks one that merely shares
  vocabulary, and matching entities surface as chips that open their entity
  pages.
- **Time travel** — the vault is a git repo. Take a snapshot anytime; the
  graph view's timeline selector replays the knowledge graph exactly as it
  was at any snapshot — the past still knows what the present forgot.
- **Domains: your vault defines its own entity types** — put a
  ```` ```domain ```` block in any note and declare types as `LABEL: regex`:

  ~~~markdown
  ```domain
  PROJECT: \b(?:Phoenix|Icarus) Project\b
  TICKET: \bENG-\d+\b
  ```
  ~~~

  Domain types are extracted across the whole vault with higher confidence
  than the generic patterns (they win on overlap), get their own colors in
  the editor, panel, and graph canvas, and flow through everything —
  entity pages, search chips, inference, PageRank. Built-in labels can't
  be shadowed; malformed regexes contribute nothing.

  Lines with `{TYPE}` placeholders declare **typed relations**:
  `BLOCKS: {TICKET} blocks {PROJECT}` turns "ENG-42 blocks the Icarus
  Project rollout" into a `blocks` edge between the two typed entities —
  components must appear in order within one sentence, filler words
  allowed. Template edges carry sentence evidence and feed conflicts and
  inference like any extracted relation.
- **Live query notes** — a ```` ```query ```` block renders always-current
  results in the panel, one query per line:

  ~~~markdown
  ```query
  relations blocks
  entities TICKET
  ?- empire_builder(P, B)
  ```
  ~~~

  `entities LABEL`, `relations predicate`, and `connected Entity Name`
  query the graph; `?- pred(X, Y)` runs a Datalog query against the
  vault's facts *and your own rules*. Results update on every save —
  Dataview, but against a knowledge graph with a reasoner behind it.
- **Document sources: PDF, HTML, DOCX, TXT** — drop a file into the vault
  (the **+ Doc** button, or just copy it in). Text is extracted (`pypdf`
  for PDFs; stdlib parsers for HTML — scripts/styles stripped — and DOCX)
  and runs through the exact same pipeline: entities and relations
  (including your domain types), sentence evidence pointing back into the
  document, search, suggestions, inference, and queries all treat it as a
  read-only source alongside your Markdown notes. Scanned/image-only PDFs
  need OCR and are rejected with a clear error.
- **Chronology** — the Timeline view orders every dated fact across the
  whole vault: ISO dates, "March 1948", "12/06/1952", or bare years,
  found in Markdown prose or inside PDFs, Word documents, and HTML pages
  alike. Each event shows the exact sentence, its source (with format
  badge), and clickable chips for the entities involved. An **entity
  lifeline chart** heads the view: each key entity gets a track on a
  shared year axis with a dot per dated event — hover for the sentence,
  click a dot to jump to its event, click a name to open the entity
  page.
- **Your rules program the reasoner** — put a ```` ```datalog ```` block in
  any note and its Horn clauses join the inference engine:

  ~~~markdown
  ```datalog
  empire_builder(P, B) :- rel(C, P, founded_by), rel(B, C, acquired_by)
  ```
  ~~~

  Derived facts show up as inferred connections, citing your rule and the
  note it lives in. `rel(Subject, Object, predicate)` are extracted
  relations; `comention(A, B, note)` are co-mentions.

<p>
  <img src="docs/screenshot.png" alt="Graphier editor" width="70%" />
  <img src="docs/panel-intelligence.png" alt="Vault intelligence panel" width="19%" />
</p>

![Graph canvas](docs/graph-view.png)

![Entity page](docs/entity-page.png)

## The vault's history, drawn

Chronology treats time as a first-class dimension of the graph. Every
dated fact — an ISO date in Markdown prose, "March 1948" inside a Word
document, "12/06/1952" in a PDF — is parsed to a sortable key and becomes
an event that knows its exact sentence, its source, and its cast.

The **entity lifeline chart** heads the Timeline view: each key entity
gets a track on a shared year axis, a dot per dated event, and a lifeline
from first to last appearance — so "who was active when" reads at a
glance. Hover a dot for the date, source, and quoted sentence; click it to
jump to the event card; click a name to open the entity page.

![Entity lifelines](docs/lifelines.png)

Below the chart, the event list groups the same facts by year — each card
quotes its sentence verbatim, links its source with a format badge
(PDF/DOCX/HTML for documents, none for notes), and offers the entities
involved as clickable chips. Structured and unstructured sources
interleave on one axis: a board decision recorded in a DOCX sits between
two facts stated in your own notes, provenance intact either way.

![Timeline](docs/timeline.png)

## Where Graphier sits

Graphier gets compared to two very different things: Obsidian (the
workspace it feels like) and Semantica (the engine room it borrows
from). All three occupy different layers:

| | [Obsidian](https://obsidian.md) | [Semantica](https://github.com/semantica-agi/semantica) | **Graphier** |
|---|---|---|---|
| **What it is** | Note-taking app for humans | Python framework for AI-agent context | Knowledge workspace for humans, built on a real graph |
| **Who uses it** | A person taking notes | Developers building agent systems | A person taking notes (and their AI, via MCP) |
| **How the graph is made** | You draw `[[links]]` by hand | Your code pipes data through its pipeline | Extracted automatically from what you write |
| **Graph semantics** | Untyped links between notes | Typed KG (RDF/LPG), ontology-governed | Typed entities + relations, user-definable in Markdown |
| **Reasoning** | — | Forward chaining, Rete, Datalog, SPARQL | Datalog inference; your notes carry the rules |
| **Contradiction handling** | Notes silently disagree | Conflict detection framework | Conflicts flagged with both sources quoted |
| **"Why is this true?"** | — | W3C PROV-O provenance records | Every claim quotes its exact source sentence |
| **Time** | File history via plugins | Temporal KG module | Git snapshots + graph replay + lifeline chronology |
| **Sources** | Markdown (+ plugins) | Anything you pipe in (incl. Databricks/Snowflake) | Markdown, PDF, DOCX, HTML, TXT — one pipeline |
| **Queries** | Search, Dataview plugin | SPARQL/Cypher/Datalog APIs | ```` ```query ```` blocks in notes + Datalog + MCP |
| **AI involvement** | Optional plugins | Serves context *to* agents | None required; MCP server lets AI query the graph |
| **Runs as** | Desktop/mobile app | `pip install` library / infra | Self-hosted web app (Docker/pip) |
| **Best at** | Writing, ecosystem, polish | Enterprise agent infrastructure | Notes that become queryable, provable knowledge |

The relationship, in one line each: Obsidian is where Graphier gets its
*philosophy* (local-first, your files, plain Markdown); Semantica is where
it gets three *engine parts* (pattern extraction, the Datalog reasoner,
PageRank); the product in between — the self-building, self-explaining,
self-programmable vault — is Graphier.

## Run it

**pip** (once v0.1.0 is on PyPI):

```bash
pip install graphier && graphier setup   # setup fetches the extraction engine — no multi-GB ML downloads
GRAPHIER_VAULT=~/notes graphier --demo
```

**Docker (one command, demo content included):**

```bash
docker build -t graphier . && docker run -p 8000:8000 -e GRAPHIER_DEMO=1 \
  -v graphier-vault:/vault graphier
```

Open http://127.0.0.1:8000 — a seeded demo vault shows extraction, domains,
rules, queries, conflicts, and the timeline working out of the box. Mount a
host folder instead (`-v ./vault:/vault`) to use your own notes.

**From source** — backend (Python 3.10+):

```bash
python3 -m venv .venv
# Lean install: pattern-based extraction only, no ML downloads
.venv/bin/pip install --no-deps semantica
.venv/bin/pip install numpy pandas fastapi "uvicorn[standard]"
# (Or `pip install -e backend` for the full Semantica install with ML extras.)
```

Frontend (Node 18+):

```bash
cd frontend
npm install
npm run build        # served by the backend from frontend/dist
```

Start:

```bash
GRAPHIER_VAULT=./vault .venv/bin/python -m uvicorn graphier.main:create_app \
    --factory --app-dir backend --port 8000
```

Open http://127.0.0.1:8000 — create a note and start typing (append
`--demo` or set `GRAPHIER_DEMO=1` to seed the demo vault into an empty
vault). For frontend development, `npm run dev` proxies `/api` to the
backend on port 8000.

## Tests

```bash
.venv/bin/pip install pytest httpx
cd backend && ../.venv/bin/python -m pytest tests/
```

## How it fits together

```
frontend/   React + CodeMirror 6 — editor with entity underlines, entity panel
backend/    FastAPI — vault CRUD, extraction API, graph aggregation
  graphier/vault.py        Markdown files on disk (the source of truth)
  graphier/extraction.py   pattern NER/relations + domain types, cached by content hash
  graphier/graph.py        vault-wide graph: deduped entities + relation/wiki-link edges
```

The vault is always the source of truth: the graph is a derived index and can
be rebuilt from the files at any time. Extraction is deterministic (no LLM,
no network) — the pattern extractors run on an offset-preserving masked copy
of each note so spans map exactly onto what you typed.

## Ask your AI about your notes' knowledge

Graphier ships an [MCP](https://modelcontextprotocol.io/) server, so
Claude Code, Claude Desktop, Cursor — any MCP client — can query the
knowledge graph instead of doing RAG over raw text:

```json
{
  "mcpServers": {
    "graphier": {
      "command": "graphier-mcp",
      "env": { "GRAPHIER_VAULT": "/path/to/your/vault" }
    }
  }
}
```

Nine tools: `search_vault`, `get_entity` (the full dossier with quoted
mentions), `get_relations`, `query_datalog` (against your own rules),
`get_conflicts`, `get_timeline`, `list_entities`, `list_notes`,
`read_note`. Every answer carries provenance — ask "who founded Acme
Corp?" and the AI can cite both conflicting sources, sentence and all.
From a checkout, use `python -m graphier.mcp` with `--app-dir backend`
semantics (`PYTHONPATH=backend`).

## Contributing

Small codebase, 47 tests, deliberately hackable — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the 10-minute setup and
[ROADMAP.md](ROADMAP.md) for where it's going. Much of Graphier is
extensible from Markdown alone: [docs/extending.md](docs/extending.md)
shows how to add entity types, typed relations, inference rules, and live
dashboards without touching code.

## Powered by

Graphier's engine room uses three components from
[Semantica](https://github.com/semantica-agi/semantica) (MIT): the pattern
NER/relation extractors, the `DatalogReasoner` behind inference and
`?-` queries, and the `CentralityCalculator` behind PageRank insights.
Everything else — the vault model, markdown masking, domains and relation
templates, sentence-level evidence, entity pages, time travel, search,
document ingestion, the timeline, and the UI — is Graphier's own code.
Semantica's ML extractors are a drop-in upgrade path for higher-quality
extraction (`pip install semantica` without `--no-deps`).
