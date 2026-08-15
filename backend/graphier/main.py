"""Graphier API server.

Serves the vault CRUD + extraction + graph API, and the built frontend
when frontend/dist exists (single-process deployment).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .enrichment import Enricher, enrich
from .extraction import ExtractionService
from .graph import build_graph, collect_domain, entity_page
from .history import HistoryError, VaultHistory, graph_at
from .search import search as search_vault
from .vault import NoteNotFound, Vault, VaultError


class NoteCreate(BaseModel):
    title: str


class NoteUpdate(BaseModel):
    content: str


class SnapshotCreate(BaseModel):
    message: str = "snapshot"


def create_app(vault_dir: str | None = None) -> FastAPI:
    vault = Vault(vault_dir or os.environ.get("GRAPHIER_VAULT", "vault"))
    extractor = ExtractionService()
    history = VaultHistory(vault)
    app = FastAPI(title="Graphier", version="0.1.0")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "vault": str(vault.root)}

    @app.get("/api/notes")
    def list_notes():
        return [vars(n) for n in vault.list_notes()]

    @app.post("/api/notes", status_code=201)
    def create_note(body: NoteCreate):
        note_id = vault.create(body.title)
        return {"id": note_id}

    @app.get("/api/notes/{note_id}")
    def read_note(note_id: str):
        try:
            return {
                "id": note_id,
                "content": vault.read(note_id),
                "kind": vault.kind_of(note_id),
            }
        except NoteNotFound:
            raise HTTPException(404, f"note not found: {note_id}")
        except VaultError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/documents", status_code=201)
    async def upload_document(file: UploadFile):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(400, "only PDF documents are supported")
        data = await file.read()
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(413, "PDF larger than 20 MB")
        note_id = vault.save_pdf(file.filename or "document.pdf", data)
        try:
            vault.read(note_id)  # verify the text layer is extractable
        except VaultError as exc:
            vault.delete(note_id)
            raise HTTPException(400, str(exc))
        return {"id": note_id}

    @app.put("/api/notes/{note_id}")
    def update_note(note_id: str, body: NoteUpdate):
        try:
            vault.write(note_id, body.content)
        except VaultError as exc:
            raise HTTPException(400, str(exc))
        return {"id": note_id}

    @app.delete("/api/notes/{note_id}", status_code=204)
    def delete_note(note_id: str):
        try:
            vault.delete(note_id)
        except NoteNotFound:
            raise HTTPException(404, f"note not found: {note_id}")
        except VaultError as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/notes/{note_id}/entities")
    def note_entities(note_id: str):
        try:
            content = vault.read(note_id)
        except NoteNotFound:
            raise HTTPException(404, f"note not found: {note_id}")
        except VaultError as exc:
            raise HTTPException(400, str(exc))
        patterns, templates = collect_domain(vault)
        return extractor.extract(content, patterns, templates)

    @app.get("/api/graph")
    def graph(at: str | None = None):
        if at:
            try:
                return graph_at(history, extractor, at)
            except HistoryError as exc:
                raise HTTPException(400, str(exc))
        return build_graph(vault, extractor)

    @app.get("/api/search")
    def search(q: str):
        notes = {meta.id: vault.read(meta.id) for meta in vault.list_notes()}
        graph_data = build_graph(vault, extractor)
        return search_vault(q, notes, graph_data["note_titles"], graph_data)

    @app.get("/api/history")
    def list_history():
        return {"snapshots": history.list_snapshots()}

    @app.post("/api/history/snapshot", status_code=201)
    def create_snapshot(body: SnapshotCreate):
        try:
            return history.snapshot(body.message)
        except HistoryError as exc:
            raise HTTPException(500, str(exc))

    @app.get("/api/enrichment")
    def enrichment():
        return enrich(build_graph(vault, extractor))

    @app.get("/api/query")
    def run_query(q: str):
        q = q.strip()
        if not q:
            raise HTTPException(400, "empty query")
        graph_data = build_graph(vault, extractor)
        display = {n["id"]: n["text"] for n in graph_data["nodes"]}

        if q.startswith("?-"):
            pattern = q[2:].strip()
            try:
                rows = Enricher(graph_data).datalog_query(pattern)
            except Exception as exc:
                raise HTTPException(400, f"bad datalog query: {exc}")
            return {"kind": "datalog", "columns": list(rows[0]) if rows else [], "rows": rows}

        parts = q.split(None, 1)
        command, arg = parts[0].lower(), (parts[1].strip() if len(parts) > 1 else "")
        if command == "entities" and arg:
            hits = [
                {"id": n["id"], "text": n["text"], "label": n["label"], "count": n["count"]}
                for n in graph_data["nodes"]
                if n["label"] == arg.upper()
            ]
            return {"kind": "entities", "rows": hits}
        if command == "relations" and arg:
            hits = [
                {
                    "source": display.get(e["source"], e["source"]),
                    "predicate": e["predicate"],
                    "target": display.get(e["target"], e["target"]),
                    "notes": e["notes"],
                }
                for e in graph_data["edges"]
                if e["predicate"] == arg.lower().replace(" ", "_")
            ]
            return {"kind": "relations", "rows": hits}
        if command == "connected" and arg:
            wanted = arg.strip().lower()
            node = next(
                (n for n in graph_data["nodes"] if n["text"].strip().lower() == wanted), None
            )
            if node is None:
                return {"kind": "connected", "rows": []}
            neighbors = []
            for e in graph_data["edges"]:
                if node["id"] == e["source"]:
                    neighbors.append(
                        {"text": display.get(e["target"]), "predicate": e["predicate"]}
                    )
                elif node["id"] == e["target"]:
                    neighbors.append(
                        {"text": display.get(e["source"]), "predicate": e["predicate"]}
                    )
            return {"kind": "connected", "rows": neighbors}
        raise HTTPException(
            400,
            "unknown query — use 'entities LABEL', 'relations predicate', "
            "'connected Entity Name', or '?- pred(X, Y)'",
        )

    @app.get("/api/entity")
    def entity(id: str):
        graph_data = build_graph(vault, extractor)
        page = entity_page(graph_data, id)
        if page is None:
            raise HTTPException(404, f"entity not found: {id}")
        # Vault-level intelligence scoped to this entity.
        enrichment_data = enrich(graph_data)
        text = page["node"]["text"]
        page["inferred"] = [
            i for i in enrichment_data["inferred"] if text in (i["source"], i["target"])
        ]
        page["conflicts"] = [
            c
            for c in enrichment_data["conflicts"]
            if c["subject"] == text or any(cl["object"] == text for cl in c["claims"])
        ]
        return page

    @app.get("/api/notes/{note_id}/suggestions")
    def note_suggestions(note_id: str):
        try:
            vault.read(note_id)
        except NoteNotFound:
            raise HTTPException(404, f"note not found: {note_id}")
        except VaultError as exc:
            raise HTTPException(400, str(exc))
        return {"suggestions": Enricher(build_graph(vault, extractor)).suggestions_for(note_id)}

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = (dist / path).resolve()
            if path and candidate.is_relative_to(dist) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        create_app(),
        host=os.environ.get("GRAPHIER_HOST", "127.0.0.1"),
        port=int(os.environ.get("GRAPHIER_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
