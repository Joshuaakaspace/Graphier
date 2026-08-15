"""Demo vault: seeds a small, self-explanatory corpus on first launch.

Exercises every feature — extraction, wiki-links, domains, relation
templates, custom rules, live queries, conflicts, and the timeline — so
a first run shows the product instead of an empty screen.
"""

from __future__ import annotations

from .vault import Vault

DEMO_NOTES = {
    "welcome": """# Welcome

Graphier builds a knowledge graph from what you write — deterministically,
with no LLM. Open [[Research Log]] and start typing: people, organizations,
and dates light up as extraction runs. Check the Graph and Timeline views,
and click any entity name to see everything the vault knows about it,
down to the exact sentence.
""",
    "research-log": """# Research Log

Ada Lovelace founded Acme Corp in London on 2024-03-01.
She met Charles Babbage at the Royal Society to discuss the
[[Analytical Engine]] project.

Acme Corp acquired Widget Inc in 2025. Grace Hopper joined
Acme Corp as chief engineer.
""",
    "history": """# History

Grace Hopper founded Acme Corp, according to the old records.
Turing Ltd was founded by Alan Turing in March 1948.
Alan Turing met Ada Lovelace at Bletchley Manor in 1942.
""",
    "domain": """# Domain

This vault tracks engineering projects. These lines teach the extractor
new entity types and typed relations:

```domain
PROJECT: \\b(?:Phoenix|Icarus) Project\\b
TICKET: \\bENG-\\d+\\b
BLOCKS: {TICKET} blocks {PROJECT}
```
""",
    "sprint-log": """# Sprint Log

Ada Lovelace kicked off the Phoenix Project at Acme Corp.
ENG-42 blocks the Icarus Project rollout. ENG-42 was filed
by Grace Hopper on 2026-08-01.
""",
    "rules": """# Rules

Vault inference rules — these program the reasoner:

```datalog
% founders of companies that acquired others are empire builders
empire_builder(P, B) :- rel(C, P, founded_by), rel(B, C, acquired_by)
```
""",
    "dashboard": """# Dashboard

Live queries — results update on every save:

```query
relations blocks
entities TICKET
?- empire_builder(P, B)
```
""",
}


def seed_demo(vault: Vault) -> bool:
    """Populate an empty vault with the demo corpus. No-op otherwise."""
    if vault.list_notes():
        return False
    for note_id, content in DEMO_NOTES.items():
        vault.write(note_id, content)
    return True
