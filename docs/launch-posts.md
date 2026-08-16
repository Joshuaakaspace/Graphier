# Launch posts — ready to adapt and publish

Drafts, not scripts: adjust anything that doesn't sound like you. The one
rule that matters everywhere: be present in the comments for the first
day, answer fast, and concede real limitations without being asked twice.

---

## Show HN

**Title** (pick one; the first is safest):

> Show HN: An Obsidian-like app where the knowledge graph builds itself (no LLM)

> Show HN: Graphier – notes that extract their own knowledge graph, with provenance

**URL:** https://github.com/ioteverythin/Graphier

**First comment** (post immediately after submitting):

> Hi HN — I built Graphier because I wanted Obsidian's graph to actually
> *mean* something. In Obsidian, the graph shows links you drew by hand.
> Graphier extracts a typed knowledge graph from what you write — people,
> orgs, dates, relations like "founded_by" — and every edge can quote the
> exact sentence it came from.
>
> The contrarian part: there's **no LLM anywhere in the pipeline**. Same
> vault in, same graph out, every time, offline. Extraction is
> pattern-based, inference is a Datalog reasoner, and the whole graph
> rebuilds from your Markdown files (plus PDFs/DOCX/HTML you drop in).
> The tradeoff is real: regex-tier extraction is noisier than an LLM on
> free prose. What you get in exchange is determinism and provenance —
> the app can never tell you something it can't point to in your own
> files.
>
> The features I'm most fond of:
>
> - Your notes program the system: a ```domain block defines entity
>   types, ```datalog blocks add inference rules ("founders of companies
>   that acquired others are empire builders"), ```query blocks render
>   live dashboards.
> - Conflict detection: two documents disagreeing about who founded a
>   company gets flagged with both sentences quoted.
> - Time travel: the vault is a git repo; the graph view can replay what
>   you knew at any snapshot.
> - An MCP server, so Claude/Cursor can query the *graph* instead of
>   doing RAG over raw text — with citations.
> - It's also a Python library: `graphier.open("~/notes").plot_graph()`.
>
> Try it in one command (seeded demo included):
> `docker run -p 8000:8000 -e GRAPHIER_DEMO=1 ghcr-or-build...` — or
> `pip install graphier && graphier setup`.
>
> Deliberately out of scope: cloud sync, mobile, and any required AI.
> Deliberately in scope next (based on what you tell me): Obsidian vault
> import, OCR, conflict-resolution workflow.
>
> Would love tough questions — especially from people who've tried to
> make extraction-based PKM work before and hit the noise wall.

**Predictable questions — have answers ready:**

- *"Regex NER? Won't that be noisy?"* — Yes, and it's the honest trade.
  Domain blocks let you define precise types for what you care about; the
  full-Semantica install swaps in ML extractors behind the same interface;
  and everything shows confidence + evidence so noise is visible, not
  silent.
- *"Why not embeddings?"* — Embeddings are unexplainable and
  nondeterministic; this project's thesis is that a personal knowledge
  base should be auditable. Optional semantic search is on the roadmap as
  exactly that — optional.
- *"Obsidian has plugins for X"* — Probably true; the difference is the
  typed graph + reasoner + provenance core, which a plugin can't retrofit.
- *"Is this a Semantica demo?"* — It uses three engine components from
  Semantica (MIT); the vault model, provenance, domains/rules/queries,
  and all UI are Graphier's. There's a comparison table in the README.

---

## r/ObsidianMD

**Title:**
> I built an experiment: what if the graph view built itself? (no AI, every edge cites its sentence)

**Body:**

> Long-time graph-view lover, always slightly disappointed that it only
> shows links I manually made. So I built Graphier — an Obsidian-*like*
> app (plain Markdown vault, local-first, your files) where a
> deterministic extractor builds a typed graph as you write: people,
> orgs, projects, dates, relations like "founded by". Click any edge and
> it quotes the exact sentence that created it.
>
> It's not an Obsidian replacement — you'd miss your plugins, mobile,
> and the editor polish. It's a different answer to the question "what
> should a notes graph *be*?" Things it does that I haven't seen
> elsewhere: fenced code blocks that define your own entity types and
> inference rules, contradiction detection between notes, and replaying
> the graph as it was at any git snapshot.
>
> Demo GIF in the repo; runs in one Docker command with seeded content.
> Would genuinely love this community's take — especially "here's a case
> where the extraction falls flat" reports. [link]

---

## r/PKMS

**Title:**
> Graphier: a PKM where notes compile into a queryable knowledge graph (typed entities, Datalog, provenance)

**Body:**

> The pitch in one line: Dataview queries file metadata you wrote;
> Graphier queries *facts extracted from your prose* — and can also
> derive new ones with rules you write in your notes.
>
> ```datalog
> empire_builder(P, B) :- rel(C, P, founded_by), rel(B, C, acquired_by)
> ```
>
> …put that in any note and "Ada founded Acme; Acme acquired Widget"
> across two different files derives "Ada ↔ Widget", citing the rule and
> both sentences. Also: user-defined entity types via regex, a
> chronology view that orders every dated fact across Markdown + PDF +
> DOCX sources, and conflict detection when files disagree.
>
> No LLM, no cloud, MIT. Curious how this lands with people deep in
> Tana/Capacities-style typed notes — this is the "types without manual
> tagging" experiment. [link]

---

## r/selfhosted

**Title:**
> Graphier — self-hosted notes that build their own knowledge graph. One container, no external services, no AI calls.

**Body:**

> Single container, single volume, zero external dependencies at
> runtime — no LLM APIs, no telemetry, nothing phones home. Your notes
> are plain Markdown in the volume; the knowledge graph, search,
> timeline, and inference are all derived locally and rebuild from the
> files. `docker run -p 8000:8000 -e GRAPHIER_DEMO=1 -v graphier:/vault …`
> gets you a seeded demo. MIT, FastAPI + React, 60+ tests. [link]

---

## Short blurbs

**lobste.rs** (tag: `practices`, `web`): submit the repo link with title
"Graphier: an Obsidian-like workspace where the knowledge graph builds
itself (no LLM)" — no self-promo text needed, be in comments.

**X / Mastodon thread opener:**

> Obsidian's graph shows links you drew. I built one where the graph
> builds itself — typed entities, extracted relations, inference rules
> you write inside your notes, and every single edge can quote the
> sentence it came from. No LLM anywhere. 🧵 [GIF]

**awesome-lists PRs:** `awesome-selfhosted` (Note-taking category),
`awesome-mcp-servers` (knowledge/search category — cite the nine tools),
`awesome-knowledge-management`.
