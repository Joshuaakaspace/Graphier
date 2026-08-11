import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    for title, body in [
        ("Research Log", "# Research Log\n\nAda Lovelace founded Acme Corp.\nAcme Corp acquired Widget Inc in 2025."),
        ("History", "# History\n\nGrace Hopper founded Acme Corp, according to old records."),
        ("Meeting Notes", "# Meeting Notes\n\nGrace Hopper met Alan Turing at Bletchley Manor."),
    ]:
        note_id = c.post("/api/notes", json={"title": title}).json()["id"]
        c.put(f"/api/notes/{note_id}", json={"content": body})
    return c


def test_chained_inference_with_explanation(client):
    inferred = client.get("/api/enrichment").json()["inferred"]
    chained = [i for i in inferred if i["kind"] == "chained"]
    assert any(
        i["source"] == "Widget Inc" and i["target"] == "Ada Lovelace" for i in chained
    ), chained
    hit = next(i for i in chained if i["target"] == "Ada Lovelace")
    assert "acquired by" in hit["because"] and "founded by" in hit["because"]


def test_bridged_inference_only_across_notes(client):
    inferred = client.get("/api/enrichment").json()["inferred"]
    for item in inferred:
        if item["kind"] == "bridged":
            # bridged pairs must never co-occur in a single note
            assert "never appear together" in item["because"]
            assert "1942" not in (item["source"], item["target"])  # no DATE bridges


def test_conflict_detected_across_notes(client):
    conflicts = client.get("/api/enrichment").json()["conflicts"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["subject"] == "Acme Corp"
    assert conflict["predicate"] == "founded by"
    objects = {c["object"] for c in conflict["claims"]}
    assert objects == {"Ada Lovelace", "Grace Hopper"}
    note_ids = {n["id"] for c in conflict["claims"] for n in c["notes"]}
    assert note_ids == {"research-log", "history"}


def test_insights_rank_central_entities(client):
    insights = client.get("/api/enrichment").json()["insights"]
    assert insights, "expected at least one insight"
    texts = [i["text"] for i in insights]
    assert "Acme Corp" in texts or "Grace Hopper" in texts
    assert all(i["label"] != "DATE" for i in insights)
    scores = [i["score"] for i in insights]
    assert scores == sorted(scores, reverse=True)


def test_suggestions_surface_cross_note_entities(client):
    res = client.get("/api/notes/research-log/suggestions").json()["suggestions"]
    grace_or_acme = [s for s in res if s["text"] in ("Acme Corp",)]
    assert grace_or_acme, res
    assert any(other["id"] == "history" for other in grace_or_acme[0]["also_in"])


def test_custom_datalog_rules_from_notes(client):
    body = (
        "# Rules\n\nMy vault rules:\n\n"
        "```datalog\n"
        "% anyone who founded a company that acquired another is an empire builder\n"
        "empire_builder(P, B) :- rel(C, P, founded_by), rel(B, C, acquired_by)\n"
        "```\n"
    )
    note_id = client.post("/api/notes", json={"title": "Rules"}).json()["id"]
    client.put(f"/api/notes/{note_id}", json={"content": body})

    graph = client.get("/api/graph").json()
    assert len(graph["custom_rules"]) == 1
    assert graph["custom_rules"][0]["note"] == "rules"

    inferred = client.get("/api/enrichment").json()["inferred"]
    custom = [i for i in inferred if i["kind"] == "custom"]
    assert any(
        i["source"] == "Ada Lovelace" and i["target"] == "Widget Inc" for i in custom
    ), custom
    hit = next(i for i in custom if i["source"] == "Ada Lovelace")
    assert "your rule in Rules" in hit["because"]


def test_rule_blocks_not_extracted_as_entities(client):
    body = "# Rules Two\n\n```datalog\nFriend Of Mine(X) :- comention(X, Y, N)\n```\n"
    note_id = client.post("/api/notes", json={"title": "Rules Two"}).json()["id"]
    client.put(f"/api/notes/{note_id}", json={"content": body})
    entities = client.get(f"/api/notes/{note_id}/entities").json()["entities"]
    assert entities == []


def test_reserved_and_malformed_rules_ignored(client):
    body = (
        "# Bad Rules\n\n```datalog\n"
        "rel(X, Y) :- comention(X, Y, N)\n"
        "broken( :- nonsense\n"
        "```\n"
    )
    note_id = client.post("/api/notes", json={"title": "Bad Rules"}).json()["id"]
    client.put(f"/api/notes/{note_id}", json={"content": body})
    result = client.get("/api/enrichment").json()
    assert all(i["kind"] != "custom" for i in result["inferred"])


def test_edges_carry_sentence_evidence(client):
    graph = client.get("/api/graph").json()
    founded = next(
        e for e in graph["edges"]
        if e["predicate"] == "founded_by" and "research-log" in e["notes"]
    )
    assert founded["evidence"], founded
    sentence = founded["evidence"][0]["sentence"]
    assert "Ada Lovelace" in sentence and "founded" in sentence


def test_entity_page_mentions_relations_and_conflicts(client):
    page = client.get("/api/entity", params={"id": "ORG:acme corp"}).json()
    assert page["node"]["text"] == "Acme Corp"

    assert any(
        "founded Acme Corp" in m["sentence"] and m["title"] == "Research Log"
        for m in page["mentions"]
    ), page["mentions"]

    rel = next(r for r in page["relations"] if r["predicate"] == "founded_by")
    assert rel["evidence"][0]["sentence"]

    assert page["conflicts"] and page["conflicts"][0]["subject"] == "Acme Corp"
    assert any("Acme Corp" in (i["source"], i["target"]) for i in page["inferred"])


def test_entity_page_unknown_id_404(client):
    assert client.get("/api/entity", params={"id": "ORG:nonexistent"}).status_code == 404
