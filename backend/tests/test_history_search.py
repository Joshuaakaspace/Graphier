import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    for title, body in [
        ("Research Log", "# Research Log\n\nAda Lovelace founded Acme Corp in London."),
        ("Meeting Notes", "# Meeting Notes\n\nGrace Hopper presented the compiler roadmap."),
    ]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    return c


# ---- search ----

def test_search_ranks_relevant_note_first(client):
    result = client.get("/api/search", params={"q": "compiler roadmap"}).json()
    assert result["results"], result
    assert result["results"][0]["id"] == "meeting-notes"
    assert "compiler" in result["results"][0]["snippet"].lower()


def test_search_entity_match_boosts_and_returns_entity(client):
    result = client.get("/api/search", params={"q": "ada lovelace"}).json()
    assert result["results"][0]["id"] == "research-log"
    assert any(
        e["text"] == "Ada Lovelace" and e["label"] == "PERSON" for e in result["entities"]
    )


def test_search_term_coverage_beats_repetition(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    for title, body in [
        ("Spam", "# Spam\n\n" + "compiler " * 40),
        ("Plan", "# Plan\n\nThe compiler roadmap was finalized this week."),
    ]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    result = c.get("/api/search", params={"q": "compiler roadmap"}).json()
    assert [r["id"] for r in result["results"]][0] == "plan"


def test_search_length_normalization_and_score_range(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    filler = " ".join(f"word{i}" for i in range(300))
    for title, body in [
        ("Short", "# Short\n\nThe roadmap."),
        ("Long", f"# Long\n\nThe roadmap. {filler}"),
    ]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    result = c.get("/api/search", params={"q": "roadmap"}).json()
    ids = [r["id"] for r in result["results"]]
    assert ids[0] == "short"
    # normalized BM25: lexical score is bounded by 1 (no entity boost here)
    assert all(0 < r["score"] <= 1 for r in result["results"])


def test_search_empty_query_and_no_hits(client):
    assert client.get("/api/search", params={"q": "   "}).json()["results"] == []
    assert client.get("/api/search", params={"q": "zzzqqqxxx"}).json()["results"] == []


# ---- history / time travel ----

def test_snapshot_history_and_graph_at(client):
    first = client.post("/api/history/snapshot", json={"message": "v1"}).json()
    assert first["created"] and first["sha"]

    # nothing changed -> no new snapshot
    again = client.post("/api/history/snapshot", json={"message": "noop"}).json()
    assert again["created"] is False

    # change the vault: Acme Corp is acquired
    client.put(
        "/api/notes/research-log",
        json={"content": "# Research Log\n\nMega Holdings acquired Acme Corp."},
    )
    second = client.post("/api/history/snapshot", json={"message": "v2"}).json()
    assert second["created"]

    snapshots = client.get("/api/history").json()["snapshots"]
    assert [s["message"] for s in snapshots] == ["v2", "v1"]

    # the past still knows what the present forgot
    old_graph = client.get("/api/graph", params={"at": first["sha"]}).json()
    old_texts = {n["text"] for n in old_graph["nodes"]}
    assert "Ada Lovelace" in old_texts

    new_graph = client.get("/api/graph").json()
    new_texts = {n["text"] for n in new_graph["nodes"]}
    assert "Ada Lovelace" not in new_texts
    assert "Mega Holdings" in new_texts


def test_graph_at_bad_ref_rejected(client):
    client.post("/api/history/snapshot", json={"message": "v1"})
    assert client.get("/api/graph", params={"at": "no such; ref"}).status_code == 400
