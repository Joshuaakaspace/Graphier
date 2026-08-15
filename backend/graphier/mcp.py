"""Graphier MCP server: the vault's knowledge, queryable by AI tools.

A Model Context Protocol server over stdio (newline-delimited JSON-RPC
2.0) exposing the knowledge graph — not raw text — to Claude Code,
Claude Desktop, Cursor, and any other MCP client. Every answer carries
the same sentence-level provenance as the app: the AI can always say
which sentence, in which source, justified a claim.

Run:  GRAPHIER_VAULT=/path/to/vault graphier-mcp
      (or python -m graphier.mcp)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from .enrichment import Enricher, enrich
from .extraction import ExtractionService
from .graph import build_graph, entity_page
from .search import search as search_vault
from .timeline import build_timeline
from .vault import NoteNotFound, Vault, VaultError

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "graphier", "version": "0.1.0"}


class GraphierTools:
    """Tool implementations over one vault. The graph is rebuilt per call —
    extraction is content-hash cached, so unchanged notes cost nothing."""

    def __init__(self, vault_dir: str):
        self.vault = Vault(vault_dir)
        self.extractor = ExtractionService()

    def _graph(self) -> dict[str, Any]:
        return build_graph(self.vault, self.extractor)

    # ---- tools ----

    def search(self, query: str) -> dict[str, Any]:
        notes = {m.id: self.vault.read(m.id) for m in self.vault.list_notes()}
        graph = self._graph()
        return search_vault(query, notes, graph["note_titles"], graph)

    def get_entity(self, name: str) -> dict[str, Any]:
        graph = self._graph()
        wanted = name.strip().lower()
        node = next(
            (n for n in graph["nodes"] if n["text"].strip().lower() == wanted or n["id"] == name),
            None,
        )
        if node is None:
            candidates = [n["text"] for n in graph["nodes"] if wanted in n["text"].lower()][:5]
            return {"error": f"entity not found: {name}", "did_you_mean": candidates}
        page = entity_page(graph, node["id"]) or {}
        enrichment = enrich(graph)
        page["conflicts"] = [
            c for c in enrichment["conflicts"]
            if c["subject"] == node["text"]
            or any(cl["object"] == node["text"] for cl in c["claims"])
        ]
        page["inferred"] = [
            i for i in enrichment["inferred"] if node["text"] in (i["source"], i["target"])
        ]
        return page

    def list_entities(self, label: str | None = None) -> list[dict[str, Any]]:
        graph = self._graph()
        return [
            {"text": n["text"], "label": n["label"], "mentions": n["count"], "notes": n["notes"]}
            for n in graph["nodes"]
            if n["label"] != "NOTE" and (label is None or n["label"] == label.upper())
        ]

    def get_relations(self, predicate: str | None = None) -> list[dict[str, Any]]:
        graph = self._graph()
        display = {n["id"]: n["text"] for n in graph["nodes"]}
        wanted = predicate.lower().replace(" ", "_") if predicate else None
        return [
            {
                "subject": display.get(e["source"], e["source"]),
                "predicate": e["predicate"],
                "object": display.get(e["target"], e["target"]),
                "origin": e["origin"],
                "confidence": e["confidence"],
                "evidence": e["evidence"],
            }
            for e in graph["edges"]
            if wanted is None or e["predicate"] == wanted
        ]

    def query_datalog(self, pattern: str) -> dict[str, Any]:
        pattern = pattern.strip()
        if pattern.startswith("?-"):
            pattern = pattern[2:].strip()
        rows = Enricher(self._graph()).datalog_query(pattern)
        return {"pattern": pattern, "rows": rows}

    def get_conflicts(self) -> list[dict[str, Any]]:
        return enrich(self._graph())["conflicts"]

    def get_timeline(self, year_from: int | None = None, year_to: int | None = None) -> list[dict[str, Any]]:
        events = build_timeline(self.vault, self.extractor)
        return [
            e for e in events
            if (year_from is None or e["year"] >= year_from)
            and (year_to is None or e["year"] <= year_to)
        ]

    def list_notes(self) -> list[dict[str, Any]]:
        return [
            {"id": m.id, "title": m.title, "kind": m.kind} for m in self.vault.list_notes()
        ]

    def read_note(self, note_id: str) -> dict[str, Any]:
        try:
            return {"id": note_id, "content": self.vault.read(note_id)}
        except (NoteNotFound, VaultError) as exc:
            return {"error": str(exc)}


TOOL_DEFS = [
    {
        "name": "search_vault",
        "description": "Hybrid search over the vault: TF-IDF ranking boosted by the "
        "knowledge graph. Returns ranked note hits with snippets, plus entities "
        "matching the query.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_entity",
        "description": "Everything the vault knows about one entity: every mention "
        "quoted verbatim with its source, every relation backed by the exact "
        "sentence that asserted it, plus conflicts and inferred connections it "
        "participates in.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Entity name, e.g. 'Ada Lovelace'"}},
            "required": ["name"],
        },
    },
    {
        "name": "list_entities",
        "description": "List entities in the knowledge graph, optionally filtered by "
        "type (PERSON, ORG, GPE, DATE, CONCEPT, or any user-defined domain type).",
        "inputSchema": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
        },
    },
    {
        "name": "get_relations",
        "description": "Typed relations from the graph (founded_by, acquired_by, "
        "user-defined predicates…), each with origin, confidence, and the sentence "
        "evidence that produced it. Filter by predicate or get all.",
        "inputSchema": {
            "type": "object",
            "properties": {"predicate": {"type": "string"}},
        },
    },
    {
        "name": "query_datalog",
        "description": "Run a Datalog query against the vault's extracted facts AND "
        "the user's own inference rules. Facts: rel(Subject, Object, predicate), "
        "comention(A, B, note). Example: 'empire_builder(P, B)'. Variables start "
        "uppercase.",
        "inputSchema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "get_conflicts",
        "description": "Contradictions the vault has detected: the same subject and "
        "predicate asserted with different objects in different sources, each claim "
        "with its source notes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_timeline",
        "description": "Chronology of every dated fact across all sources (notes, "
        "PDFs, DOCX, HTML), each event with its exact sentence and source. "
        "Optionally bounded by year.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "year_from": {"type": "integer"},
                "year_to": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_notes",
        "description": "List every source in the vault (markdown notes and "
        "documents) with id, title, and kind.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_note",
        "description": "Read one source's full text (markdown content, or the "
        "extracted text of a PDF/DOCX/HTML document).",
        "inputSchema": {
            "type": "object",
            "properties": {"note_id": {"type": "string"}},
            "required": ["note_id"],
        },
    },
]


def handle_request(tools: GraphierTools, request: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatch one JSON-RPC request. Returns None for notifications."""
    method = request.get("method", "")
    request_id = request.get("id")

    def result(payload: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": payload}

    def error(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return result(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            }
        )
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return result({})
    if method == "tools/list":
        return result({"tools": TOOL_DEFS})
    if method == "tools/call":
        params = request.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments") or {}
        handlers = {
            "search_vault": lambda: tools.search(args["query"]),
            "get_entity": lambda: tools.get_entity(args["name"]),
            "list_entities": lambda: tools.list_entities(args.get("label")),
            "get_relations": lambda: tools.get_relations(args.get("predicate")),
            "query_datalog": lambda: tools.query_datalog(args["pattern"]),
            "get_conflicts": lambda: tools.get_conflicts(),
            "get_timeline": lambda: tools.get_timeline(args.get("year_from"), args.get("year_to")),
            "list_notes": lambda: tools.list_notes(),
            "read_note": lambda: tools.read_note(args["note_id"]),
        }
        handler = handlers.get(name)
        if handler is None:
            return error(-32602, f"unknown tool: {name}")
        try:
            payload = handler()
        except KeyError as exc:
            return error(-32602, f"missing required argument: {exc}")
        except Exception as exc:  # tool errors surface as tool results, not crashes
            return result(
                {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True}
            )
        return result(
            {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=1)}]}
        )
    if request_id is None:
        return None
    return error(-32601, f"method not found: {method}")


def main() -> None:
    os.environ.setdefault("SEMANTICA_DISABLE_PROGRESS", "1")
    tools = GraphierTools(os.environ.get("GRAPHIER_VAULT", "vault"))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print(
                json.dumps(
                    {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
                ),
                flush=True,
            )
            continue
        response = handle_request(tools, request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
