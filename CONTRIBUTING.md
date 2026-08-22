# Contributing to Graphier

Thanks for looking under the hood. Graphier is deliberately small: a FastAPI
backend of ~10 focused modules and a React frontend of ~8 components, held
together by 47 tests. You can read the whole backend in an hour.

## Dev setup (10 minutes)

Backend — the lean install needs no ML downloads:

```bash
python3 -m venv .venv
.venv/bin/pip install --no-deps semantica
.venv/bin/pip install numpy pandas scipy networkx pypdf python-multipart \
    fastapi "uvicorn[standard]" pytest httpx
```

Frontend:

```bash
cd frontend && npm install
```

Run both for development (frontend proxies `/api` to the backend):

```bash
GRAPHIER_VAULT=./vault GRAPHIER_DEMO=1 .venv/bin/python -m uvicorn \
    graphier.main:create_app --factory --app-dir backend --port 8000
cd frontend && npm run dev   # in a second terminal → http://localhost:5173
```

Tests — run from `backend/` (that's also what CI does):

```bash
cd backend && ../.venv/bin/python -m pytest tests/ -q
```

## How the code is laid out

```
backend/graphier/
  vault.py        files on disk: .md notes + read-only documents (one id namespace)
  documents.py    text extractors: pypdf for PDF, stdlib for HTML/DOCX/TXT
  extraction.py   entity + relation extraction over a masked shadow of each note
  graph.py        vault-wide graph: nodes, edges, sentence evidence, domain parsing
  enrichment.py   Datalog inference, conflicts, suggestions, PageRank
  search.py       BM25 + graph-boosted hybrid search
  history.py      git-backed snapshots and graph-at-commit replay
  timeline.py     dated events across all sources
  demo.py         first-run demo corpus
  main.py         FastAPI app wiring it all together
frontend/src/
  App.tsx         layout, views, panels        Editor.tsx      CodeMirror + underlines
  GraphView.tsx   Sigma.js canvas              TimelineView.tsx / LifelineChart.tsx
  EntityView.tsx  entity pages                 api.ts          typed API client
```

## Extraction in five sentences

Every note is masked into a same-length shadow copy (markdown syntax spaced
out, headings/wiki-links/code blocks blanked, newlines turned into sentence
breaks) so extraction spans map exactly onto the raw text. Pattern NER and
user-defined domain regexes run over the shadow; domain matches win overlaps.
Relations come from pattern extraction plus `{TYPE} verb {TYPE}` templates.
Everything is cached by content hash, so unchanged notes cost nothing.
The graph, inference, search, and timeline are all derived from those spans —
which is why every claim can quote the sentence it came from.

## Ground rules

- **Determinism is the product.** No LLM calls, no network calls, no
  randomness in the extraction → graph path. (An *optional* ML extraction
  backend is fine; a *required* one is not.)
- **Every edge carries evidence.** If your feature asserts something, it must
  be able to point at the sentence (or rule) that justifies it.
- **Tests come with the PR.** Look at `backend/tests/` for the house style —
  small fixtures, end-to-end through the API.
- Keep PRs focused; one feature or fix per PR beats a grab bag.

## Where to start

Issues labeled `good first issue` are scoped to be doable without deep
context. `docs/extending.md` shows how much you can do with zero code —
sometimes a "feature request" is a domain block away.
