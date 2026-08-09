# Graphier

An Obsidian-like knowledge workspace where the graph builds itself.

You write plain Markdown notes; [Semantica](https://github.com/semantica-agi/semantica)'s
deterministic extraction pipeline turns them into a typed knowledge graph
underneath — people, organizations, places, and dates light up as you type,
relations are extracted with confidence scores, and `[[wiki-links]]` become
explicit edges. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

**Status: Phase 1 walking skeleton** — vault CRUD, live entity extraction with
in-editor underlines, entity/relations panel, and vault-wide graph aggregation.
Graph canvas, provenance panel, and reasoning are later phases.

![Graphier screenshot](docs/screenshot.png)

## Run it

Backend (Python 3.10+):

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

Open http://127.0.0.1:8000 — create a note and start typing. For frontend
development, `npm run dev` proxies `/api` to the backend on port 8000.

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
  graphier/extraction.py   Semantica pattern NER/relations, cached by content hash
  graphier/graph.py        vault-wide graph: deduped entities + relation/wiki-link edges
```

The vault is always the source of truth: the graph is a derived index and can
be rebuilt from the files at any time. Extraction is deterministic (no LLM,
no network) — Semantica's pattern extractors run on an offset-preserving
masked copy of each note so spans map exactly onto what you typed.
