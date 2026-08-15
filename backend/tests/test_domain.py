import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    domain = (
        "# Domain\n\nThis vault tracks engineering projects.\n\n"
        "```domain\n"
        "PROJECT: \\b(?:Phoenix|Icarus) Project\\b\n"
        "TICKET: \\bENG-\\d+\\b\n"
        "```\n"
    )
    note = (
        "# Sprint Log\n\nAda Lovelace kicked off the Phoenix Project.\n"
        "ENG-42 blocks the Icarus Project rollout. ENG-42 was filed by Grace Hopper.\n"
    )
    for title, body in [("Domain", domain), ("Sprint Log", note)]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    return c


def test_domain_types_extracted_with_spans(client):
    result = client.get("/api/notes/sprint-log/entities").json()
    by_label = {}
    for e in result["entities"]:
        by_label.setdefault(e["label"], set()).add(e["text"])
    assert by_label.get("PROJECT") == {"Phoenix Project", "Icarus Project"}
    assert by_label.get("TICKET") == {"ENG-42"}
    # spans still map onto the raw text
    for e in result["entities"]:
        assert e["text"]  # non-empty, sliced from original


def test_domain_beats_generic_ner_on_overlap(client):
    result = client.get("/api/notes/sprint-log/entities").json()
    # "Phoenix Project" would otherwise match the generic PERSON pattern
    assert not any(
        e["label"] == "PERSON" and "Project" in e["text"] for e in result["entities"]
    )
    # but real people are still found
    assert any(e["text"] == "Ada Lovelace" and e["label"] == "PERSON" for e in result["entities"])


def test_domain_types_flow_into_graph_and_entity_page(client):
    graph = client.get("/api/graph").json()
    assert {d["label"] for d in graph["domain_types"]} == {"PROJECT", "TICKET"}
    ticket = next(n for n in graph["nodes"] if n["label"] == "TICKET")
    assert ticket["text"] == "ENG-42"

    page = client.get("/api/entity", params={"id": "TICKET:eng-42"}).json()
    assert page["node"]["count"] == 2
    assert any("blocks the Icarus Project" in m["sentence"] for m in page["mentions"])


def test_builtin_labels_cannot_be_shadowed(client):
    note_id = client.post("/api/notes", json={"title": "Evil"}).json()["id"]
    client.put(
        f"/api/notes/{note_id}",
        json={"content": "# Evil\n\n```domain\nPERSON: .+\nBAD(: unclosed\n```\n"},
    )
    graph = client.get("/api/graph").json()
    assert all(d["label"] != "PERSON" for d in graph["domain_types"])
    # and a malformed regex contributes nothing rather than erroring
    assert client.get("/api/notes/sprint-log/entities").status_code == 200


def test_editing_domain_reextracts_other_notes(client):
    client.put(
        "/api/notes/domain",
        json={"content": "# Domain\n\n```domain\nRISK: \\brollout\\b\n```\n"},
    )
    result = client.get("/api/notes/sprint-log/entities").json()
    labels = {e["label"] for e in result["entities"]}
    assert "RISK" in labels and "PROJECT" not in labels
