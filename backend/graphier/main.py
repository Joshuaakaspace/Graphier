"""Graphier API server.

Serves the vault CRUD + extraction + graph API, and the built frontend
when frontend/dist exists (single-process deployment).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .enrichment import Enricher, enrich
from .extraction import ExtractionService
from .graph import build_graph, entity_page
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
            return {"id": note_id, "content": vault.read(note_id)}
        except NoteNotFound:
            raise HTTPException(404, f"note not found: {note_id}")
        except VaultError as exc:
            raise HTTPException(400, str(exc))

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
        return extractor.extract(content)

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
