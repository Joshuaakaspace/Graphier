# How search works

Graphier's vault search is deliberately boring in the best way: no
embeddings, no model calls, no index server. It is a small, deterministic
ranking function — the same query over the same vault returns the same
results, every time, offline. This page explains exactly what happens when
you type a query, so you can predict it, tune it, or replace it.

Everything below lives in one file:
[`backend/graphier/search.py`](../backend/graphier/search.py) (~120 lines,
stdlib only).

## The pipeline

A query goes through four steps:

1. **Tokenize** — lowercase, split on runs of `[a-z0-9]+`. Punctuation,
   Markdown syntax, and case disappear; `"Ada Lovelace!"` becomes
   `["ada", "lovelace"]`. The same tokenizer is applied to every note body
   (documents like PDFs contribute their extracted text).

2. **Score notes lexically with BM25** — the classic Okapi BM25 ranking
   function, computed from scratch on each request:

   ```
   score(note) = Σ over query terms t of
       idf(t) · tf(t) · (k1 + 1) / (tf(t) + k1 · (1 − b + b · |note| / avg_len))
   ```

   with `k1 = 1.5` and `b = 0.75` (the standard defaults), and the BM25
   inverse document frequency
   `idf(t) = ln(1 + (N − df(t) + 0.5) / (df(t) + 0.5))` where `N` is the
   number of notes and `df(t)` how many contain `t`.

   Two properties make BM25 the right default over plain TF-IDF:

   - **Term-frequency saturation** (`k1`): the 40th occurrence of
     "compiler" in a note adds almost nothing. A note that spams one query
     term cannot outrank a note that covers *all* the query terms.
   - **Length normalization** (`b`): a term match in a 20-word note means
     more than the same match buried in a 2,000-word note.

   The raw score is then divided by the query's **best achievable score**
   (every term saturated to its ceiling), mapping the lexical component
   into `[0, 1]` regardless of query length.

3. **Boost by the knowledge graph** — this is the hybrid part. Every graph
   entity whose name contains the query (or vice versa, token-normalized)
   contributes a flat **+0.35** to every note it appears in. Because the
   lexical score is normalized to at most 1.0, the boost is a strong,
   predictable signal: a note that *mentions the entity you searched for*
   reliably outranks one that merely shares vocabulary. Matched entities
   are also returned alongside the results, which is what powers the
   entity chips above the hit list in the app.

4. **Cut, sort, snippet** — notes scoring below `0.01` are dropped, the
   top 10 survive, and each hit gets a ~130-character snippet windowed
   around the first query-term occurrence in the raw note text.

## What it deliberately is not

- **Not embeddings / semantic search.** Vector search is powerful but
  unexplainable and nondeterministic across model versions. Graphier's
  thesis is that a personal knowledge base should be auditable; optional
  semantic search may arrive later as exactly that — optional
  ([roadmap](../ROADMAP.md)).
- **Not a persistent index.** The vault is small by web-search standards
  (thousands of notes, not millions of pages), so scoring on request keeps
  the implementation transparent and always in sync with the files — there
  is no index to corrupt or rebuild.
- **Not fuzzy.** Typos don't match. The graph boost softens this in
  practice: entity names matched via the graph often rescue queries that
  lexical scoring alone would miss.

## Tuning it

All the knobs are module constants in `search.py`:

| Constant | Default | Effect of raising it |
| --- | --- | --- |
| `_K1` | `1.5` | repeated terms keep adding score for longer |
| `_B` | `0.75` | long notes are penalized harder |
| `_ENTITY_BOOST` | `0.35` | graph mentions dominate lexical relevance more |

The search endpoint is `GET /api/search?q=…`, the MCP tool is
`search_vault`, and the library exposes the same ranking through the HTTP
API. All three share this one implementation.
