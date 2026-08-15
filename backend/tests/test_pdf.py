import pytest
from fastapi.testclient import TestClient

from graphier.main import create_app


def make_pdf(text: str) -> bytes:
    """A minimal single-page PDF with a real text layer."""
    stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(vault_dir=str(tmp_path)))


def _upload(client, text, name="report.pdf"):
    return client.post(
        "/api/documents", files={"file": (name, make_pdf(text), "application/pdf")}
    )


def test_pdf_upload_lists_and_reads(client):
    res = _upload(client, "Ada Lovelace founded Acme Corp in London.")
    assert res.status_code == 201
    note_id = res.json()["id"]
    assert note_id == "report"

    listing = client.get("/api/notes").json()
    entry = next(n for n in listing if n["id"] == note_id)
    assert entry["kind"] == "pdf"

    note = client.get(f"/api/notes/{note_id}").json()
    assert note["kind"] == "pdf"
    assert "Ada Lovelace founded Acme Corp" in note["content"]


def test_pdf_feeds_graph_and_search(client):
    _upload(client, "Grace Hopper founded Turing Ltd in 1952.")
    graph = client.get("/api/graph").json()
    texts = {n["text"] for n in graph["nodes"]}
    assert "Grace Hopper" in texts and "Turing Ltd" in texts

    founded = next(e for e in graph["edges"] if e["predicate"] == "founded_by")
    assert founded["evidence"][0]["note"] == "report"
    assert "Grace Hopper founded Turing Ltd" in founded["evidence"][0]["sentence"]

    hits = client.get("/api/search", params={"q": "grace hopper"}).json()["results"]
    assert hits and hits[0]["id"] == "report"


def test_pdf_is_read_only(client):
    note_id = _upload(client, "Immutable facts.").json()["id"]
    res = client.put(f"/api/notes/{note_id}", json={"content": "overwrite"})
    assert res.status_code == 400
    assert "read-only" in res.json()["detail"]


def test_pdf_delete_and_reject_non_pdf(client):
    note_id = _upload(client, "Temp.").json()["id"]
    assert client.delete(f"/api/notes/{note_id}").status_code == 204
    assert client.get(f"/api/notes/{note_id}").status_code == 404

    bad = client.post("/api/documents", files={"file": ("x.txt", b"hi", "text/plain")})
    assert bad.status_code == 400


def test_broken_pdf_rejected_cleanly(client):
    res = client.post(
        "/api/documents", files={"file": ("bad.pdf", b"%PDF-not really", "application/pdf")}
    )
    assert res.status_code == 400
    assert all(n["id"] != "bad" for n in client.get("/api/notes").json())
