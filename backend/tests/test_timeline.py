import sys

import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_pdf import make_docx, make_pdf  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    c = TestClient(create_app(vault_dir=str(tmp_path)))
    # Unstructured: markdown prose
    note_id = c.post("/api/notes", json={"title": "Research Log"}).json()["id"]
    c.put(
        f"/api/notes/{note_id}",
        json={
            "content": "# Research Log\n\n"
            "Ada Lovelace founded Acme Corp in London on 2024-03-01.\n"
            "Acme Corp acquired Widget Inc in 2025.\n"
        },
    )
    # Structured: a Word document and a PDF
    c.post(
        "/api/documents",
        files={"file": ("minutes.docx", make_docx(["Turing Ltd was founded in March 1948 by Alan Turing."]), "application/x")},
    )
    c.post(
        "/api/documents",
        files={"file": ("filing.pdf", make_pdf("Grace Hopper joined Turing Ltd on 12/06/1952."), "application/pdf")},
    )
    return c


def test_timeline_orders_events_across_sources(client):
    events = client.get("/api/timeline").json()["events"]
    assert len(events) >= 4
    years = [e["year"] for e in events]
    assert years == sorted(years)

    kinds = {e["kind"] for e in events}
    assert {"md", "docx", "pdf"} <= kinds


def test_timeline_dates_parsed_precisely(client):
    events = client.get("/api/timeline").json()["events"]
    iso = next(e for e in events if e["date"] == "2024-03-01")
    assert iso["sort_key"] == [2024, 3, 1]
    assert "founded Acme Corp" in iso["sentence"]

    month = next(e for e in events if e["kind"] == "docx")
    assert month["sort_key"] == [1948, 3, 0]
    assert month["date"].lower().startswith("march")

    dmy = next(e for e in events if e["kind"] == "pdf")
    assert dmy["sort_key"] == [1952, 6, 12]


def test_timeline_events_carry_cast_and_source(client):
    events = client.get("/api/timeline").json()["events"]
    iso = next(e for e in events if e["date"] == "2024-03-01")
    cast = {c["text"] for c in iso["entities"]}
    assert "Ada Lovelace" in cast and "Acme Corp" in cast
    assert iso["title"] == "Research Log" and iso["note"] == "research-log"
