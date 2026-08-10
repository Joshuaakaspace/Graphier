"""The vault: plain Markdown files on disk.

The vault is the source of truth. Everything the graph knows is derived
from these files and can be rebuilt from them at any time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class VaultError(Exception):
    pass


class NoteNotFound(VaultError):
    pass


@dataclass
class NoteMeta:
    id: str
    title: str
    modified: float
    size: int


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


class Vault:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, note_id: str) -> Path:
        # IDs are flat slugs; reject anything that could escape the vault.
        if not _ID_RE.match(note_id):
            raise VaultError(f"invalid note id: {note_id!r}")
        path = (self.root / f"{note_id}.md").resolve()
        if path.parent != self.root:
            raise VaultError(f"invalid note id: {note_id!r}")
        return path

    def list_notes(self) -> list[NoteMeta]:
        notes = []
        for path in sorted(self.root.glob("*.md")):
            stat = path.stat()
            notes.append(
                NoteMeta(
                    id=path.stem,
                    title=self._title_of(path),
                    modified=stat.st_mtime,
                    size=stat.st_size,
                )
            )
        notes.sort(key=lambda n: n.modified, reverse=True)
        return notes

    def _title_of(self, path: Path) -> str:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
                if line.strip():
                    break
        except OSError:
            pass
        return path.stem.replace("-", " ").title()

    def read(self, note_id: str) -> str:
        path = self._path(note_id)
        if not path.exists():
            raise NoteNotFound(note_id)
        return path.read_text(encoding="utf-8")

    def write(self, note_id: str, content: str) -> None:
        self._path(note_id).write_text(content, encoding="utf-8")

    def create(self, title: str) -> str:
        base = slugify(title)
        note_id, n = base, 1
        while self._path(note_id).exists():
            n += 1
            note_id = f"{base}-{n}"
        self.write(note_id, f"# {title}\n\n")
        return note_id

    def delete(self, note_id: str) -> None:
        path = self._path(note_id)
        if not path.exists():
            raise NoteNotFound(note_id)
        path.unlink()
