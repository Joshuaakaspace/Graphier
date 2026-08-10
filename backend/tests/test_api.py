import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(vault_dir=str(tmp_path)))


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_note_crud_roundtrip(client):
    note_id = client.post("/api/notes", json={"title": "Meeting Notes"}).json()["id"]
    assert note_id == "meeting-notes"

    body = "# Meeting Notes\n\nAda Lovelace founded Acme Corp in London."
    client.put(f"/api/notes/{note_id}", json={"content": body})
    assert client.get(f"/api/notes/{note_id}").json()["content"] == body

    listing = client.get("/api/notes").json()
    assert [n["id"] for n in listing] == [note_id]
    assert listing[0]["title"] == "Meeting Notes"

    assert client.delete(f"/api/notes/{note_id}").status_code == 204
    assert client.get(f"/api/notes/{note_id}").status_code == 404


def test_duplicate_titles_get_distinct_ids(client):
    first = client.post("/api/notes", json={"title": "Idea"}).json()["id"]
    second = client.post("/api/notes", json={"title": "Idea"}).json()["id"]
    assert first == "idea" and second == "idea-2"


def test_bad_note_ids_rejected(client):
    assert client.get("/api/notes/.hidden").status_code == 400
    assert client.get("/api/notes/UPPER").status_code == 400


def test_path_traversal_never_leaves_sandbox(client):
    # Encoded traversal on the API route: either rejected outright or swallowed
    # by the SPA fallback — never the target file's contents.
    for path in ["/api/notes/..%2F..%2F..%2Fetc%2Fpasswd", "/..%2F..%2F..%2Fetc%2Fpasswd"]:
        res = client.get(path)
        assert b"root:" not in res.content


def test_entities_extracted_with_spans(client):
    note_id = client.post("/api/notes", json={"title": "People"}).json()["id"]
    content = "# People\n\nAda Lovelace founded Acme Corp. See [[Analytical Engine]]."
    client.put(f"/api/notes/{note_id}", json={"content": content})

    result = client.get(f"/api/notes/{note_id}/entities").json()
    texts = {e["text"] for e in result["entities"]}
    assert "Ada Lovelace" in texts and "Acme Corp" in texts

    for ent in result["entities"]:
        assert content[ent["start"]:ent["end"]] == ent["text"]

    assert result["wikilinks"][0]["text"] == "Analytical Engine"


def test_graph_aggregates_across_notes(client):
    for title, body in [
        ("One", "# One\n\nAda Lovelace founded Acme Corp."),
        ("Two", "# Two\n\nAda Lovelace met Charles Babbage. See [[Acme Corp]]."),
    ]:
        note_id = client.post("/api/notes", json={"title": title}).json()["id"]
        client.put(f"/api/notes/{note_id}", json={"content": body})

    graph = client.get("/api/graph").json()
    ada = next(n for n in graph["nodes"] if n["text"] == "Ada Lovelace")
    assert set(ada["notes"]) == {"one", "two"}
    assert ada["count"] == 2

    manual = [e for e in graph["edges"] if e["origin"] == "manual"]
    assert len(manual) == 1
    assert manual[0]["predicate"] == "links_to"

    assert graph["summary"]["notes"] == 2
