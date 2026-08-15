import json

import pytest

from graphier.demo import seed_demo
from graphier.mcp import GraphierTools, handle_request
from graphier.vault import Vault


@pytest.fixture()
def tools(tmp_path):
    seed_demo(Vault(str(tmp_path)))
    return GraphierTools(str(tmp_path))


def call(tools, name, args=None, request_id=1):
    response = handle_request(
        tools,
        {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
         "params": {"name": name, "arguments": args or {}}},
    )
    assert "error" not in response, response
    result = response["result"]
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


def test_initialize_and_tool_list(tools):
    init = handle_request(tools, {"jsonrpc": "2.0", "id": 0, "method": "initialize"})
    assert init["result"]["serverInfo"]["name"] == "graphier"

    assert handle_request(tools, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    listing = handle_request(tools, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in listing["result"]["tools"]}
    assert names == {
        "search_vault", "get_entity", "list_entities", "get_relations",
        "query_datalog", "get_conflicts", "get_timeline", "list_notes", "read_note",
    }


def test_search_and_entity_with_provenance(tools):
    hits = call(tools, "search_vault", {"query": "ada lovelace"})
    assert hits["results"] and any(e["text"] == "Ada Lovelace" for e in hits["entities"])

    page = call(tools, "get_entity", {"name": "Acme Corp"})
    assert page["node"]["label"] == "ORG"
    assert any("founded Acme Corp" in m["sentence"] for m in page["mentions"])
    assert page["conflicts"], "demo vault has a deliberate Acme Corp conflict"

    miss = call(tools, "get_entity", {"name": "Acme"})
    assert "did_you_mean" in miss and "Acme Corp" in miss["did_you_mean"]


def test_relations_datalog_conflicts_timeline(tools):
    rels = call(tools, "get_relations", {"predicate": "founded by"})
    assert rels and all(r["predicate"] == "founded_by" for r in rels)
    assert rels[0]["evidence"][0]["sentence"]

    rows = call(tools, "query_datalog", {"pattern": "?- empire_builder(P, B)"})
    assert {"P": "Ada Lovelace", "B": "Widget Inc"} in rows["rows"]

    conflicts = call(tools, "get_conflicts")
    assert any(c["subject"] == "Acme Corp" for c in conflicts)

    events = call(tools, "get_timeline", {"year_from": 2024})
    assert events and all(e["year"] >= 2024 for e in events)


def test_notes_roundtrip_and_errors(tools):
    notes = call(tools, "list_notes")
    assert any(n["id"] == "research-log" for n in notes)
    note = call(tools, "read_note", {"note_id": "research-log"})
    assert "Ada Lovelace" in note["content"]

    unknown = handle_request(
        tools,
        {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
         "params": {"name": "no_such_tool", "arguments": {}}},
    )
    assert unknown["error"]["code"] == -32602

    bad_method = handle_request(tools, {"jsonrpc": "2.0", "id": 10, "method": "bogus"})
    assert bad_method["error"]["code"] == -32601
