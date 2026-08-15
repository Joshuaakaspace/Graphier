import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    domain = (
        "# Domain\n\n```domain\n"
        "PROJECT: \\b(?:Phoenix|Icarus) Project\\b\n"
        "TICKET: \\bENG-\\d+\\b\n"
        "BLOCKS: {TICKET} blocks {PROJECT}\n"
        "```\n"
    )
    note = (
        "# Sprint Log\n\nENG-42 blocks the Icarus Project rollout.\n"
        "Ada Lovelace founded Acme Corp. Acme Corp acquired Widget Inc.\n"
    )
    for title, body in [("Domain", domain), ("Sprint Log", note)]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    return c


def test_relation_template_extracts_typed_edge(client):
    graph = client.get("/api/graph").json()
    assert any(r["label"] == "BLOCKS" for r in graph["domain_relations"])
    blocks = next(e for e in graph["edges"] if e["predicate"] == "blocks")
    display = {n["id"]: n["text"] for n in graph["nodes"]}
    assert display[blocks["source"]] == "ENG-42"
    assert display[blocks["target"]] == "Icarus Project"
    assert "blocks the Icarus Project" in blocks["evidence"][0]["sentence"]


def test_template_middle_words_must_match(client):
    # 'ENG-42 ... Phoenix Project' without the word 'blocks' must not match —
    # the sprint note never says ENG-42 blocks Phoenix Project.
    graph = client.get("/api/graph").json()
    display = {n["id"]: n["text"] for n in graph["nodes"]}
    assert not any(
        e["predicate"] == "blocks" and display[e["target"]] == "Phoenix Project"
        for e in graph["edges"]
    )


def test_query_entities_and_relations(client):
    res = client.get("/api/query", params={"q": "entities TICKET"}).json()
    assert res["kind"] == "entities"
    assert [r["text"] for r in res["rows"]] == ["ENG-42"]

    res = client.get("/api/query", params={"q": "relations blocks"}).json()
    assert res["rows"] == [
        {
            "source": "ENG-42",
            "predicate": "blocks",
            "target": "Icarus Project",
            "notes": ["sprint-log"],
        }
    ]


def test_query_connected(client):
    res = client.get("/api/query", params={"q": "connected Acme Corp"}).json()
    texts = {r["text"] for r in res["rows"]}
    assert "Ada Lovelace" in texts and "Widget Inc" in texts


def test_query_datalog(client):
    res = client.get("/api/query", params={"q": "?- rel(X, Y, blocks)"}).json()
    assert res["kind"] == "datalog"
    assert {"X": "ENG-42", "Y": "Icarus Project"} in res["rows"]


def test_query_bad_input_rejected(client):
    assert client.get("/api/query", params={"q": "frobnicate all"}).status_code == 400
    assert client.get("/api/query", params={"q": "  "}).status_code == 400
