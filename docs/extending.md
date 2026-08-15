# Extending Graphier without writing code

Graphier is programmable from inside your own notes. Three fenced block
types — `domain`, `datalog`, and `query` — let you define entity types,
inference rules, and live dashboards in plain Markdown. They apply
vault-wide, version with your notes, and need zero code.

## Add an entity type (30 seconds)

Put this in any note:

~~~markdown
```domain
PAPER: \b[A-Z][a-zA-Z]+ et al\., \d{4}\b
DATASET: \b[A-Z][A-Z0-9]{2,}-\d+\b
```
~~~

Every note and document in the vault is immediately re-extracted with the
new types. They get their own colors in the editor, panel, graph canvas,
and search chips, and they participate in inference and PageRank like any
built-in type. Rules: `LABEL: regex`, one per line; built-in labels
(PERSON, ORG, GPE, DATE, NOTE, CONCEPT) can't be shadowed; a malformed
regex contributes nothing rather than erroring.

## Add a typed relation (1 minute)

A domain line with `{TYPE}` placeholders declares a relation extractor:

~~~markdown
```domain
CITES: {PAPER} cites {PAPER}
EVALUATED_ON: {PAPER} evaluated on {DATASET}
```
~~~

The two placeholders match entities of those types appearing in order
within one sentence — filler words allowed — so "Smith et al., 2024 was
evaluated on the IMAGENET-1k benchmark" emits an `evaluated_on` edge with
that sentence as evidence. Template edges feed conflict detection and
inference like any extracted relation.

## Teach the reasoner (2 minutes)

~~~markdown
```datalog
% a paper is influential if a paper that cites it is itself cited
influential(P) :- rel(Q, P, cites), rel(R, Q, cites)
```
~~~

Horn clauses in any `datalog` block join the vault's forward-chaining
reasoner. Available facts: `rel(Subject, Object, predicate)` for every
extracted relation and `comention(A, B, note)` for co-mentions. Derived
facts appear as inferred connections citing your rule, and are queryable.

## Build a live dashboard (1 minute)

~~~markdown
```query
entities PAPER
relations cites
connected Smith et al., 2024
?- influential(P)
```
~~~

One query per line; results render in the side panel and refresh on every
save. `?-` lines run Datalog against the vault's facts *and your rules*.

## The escape hatches that do need code

- **New document formats**: add an extractor to
  `backend/graphier/documents.py` (each is ~15 lines; see `docx_text`).
- **Better extraction**: swap the pattern method for Semantica's ML
  extractors in `extraction.py` (`NERExtractor(method="spacy")`) after a
  full `pip install semantica`.
- **New enrichment**: `enrichment.py` shows the pattern — derive from the
  graph dict, return rows with a `because`/evidence field. Nothing ships
  without provenance.
