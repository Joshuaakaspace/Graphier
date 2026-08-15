from fastapi.testclient import TestClient

from graphier.main import create_app


def test_demo_seeds_empty_vault(tmp_path):
    client = TestClient(create_app(vault_dir=str(tmp_path), demo=True))
    notes = client.get("/api/notes").json()
    ids = {n["id"] for n in notes}
    assert {"welcome", "research-log", "domain", "rules", "dashboard"} <= ids

    # The seeded corpus exercises the whole pipeline.
    graph = client.get("/api/graph").json()
    assert graph["summary"]["nodes"] > 10
    assert graph["custom_rules"] and graph["domain_types"]
    enrichment = client.get("/api/enrichment").json()
    assert enrichment["conflicts"], "demo should include a deliberate conflict"
    assert any(i["kind"] == "custom" for i in enrichment["inferred"])
    assert client.get("/api/timeline").json()["events"]


def test_demo_never_touches_populated_vault(tmp_path):
    first = TestClient(create_app(vault_dir=str(tmp_path)))
    note_id = first.post("/api/notes", json={"title": "Mine"}).json()["id"]

    again = TestClient(create_app(vault_dir=str(tmp_path), demo=True))
    ids = {n["id"] for n in again.get("/api/notes").json()}
    assert ids == {note_id}, "demo seeding must not run on a non-empty vault"
