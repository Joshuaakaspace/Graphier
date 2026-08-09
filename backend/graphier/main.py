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

from .extraction import ExtractionService
from .graph import build_graph
from .vault import NoteNotFound, Vault, VaultError


class NoteCreate(BaseModel):
    title: str


class NoteUpdate(BaseModel):
    content: str


def create_app(vault_dir: str | None = None) -> FastAPI:
    vault = Vault(vault_dir or os.environ.get("GRAPHIER_VAULT", "vault"))
    extractor = ExtractionService()
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
    def graph():
        return build_graph(vault, extractor)

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
