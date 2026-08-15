"""The vault: plain Markdown files on disk.

The vault is the source of truth. Everything the graph knows is derived
from these files and can be rebuilt from them at any time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .documents import EXTRACTORS, DocumentError

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
    kind: str = "md"  # "md" (editable note) or "pdf" (read-only document)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


class Vault:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._doc_cache: dict[str, tuple[float, str]] = {}

    def _path(self, note_id: str, suffix: str = ".md") -> Path:
        # IDs are flat slugs; reject anything that could escape the vault.
        if not _ID_RE.match(note_id):
            raise VaultError(f"invalid note id: {note_id!r}")
        path = (self.root / f"{note_id}{suffix}").resolve()
        if path.parent != self.root:
            raise VaultError(f"invalid note id: {note_id!r}")
        return path

    def list_notes(self) -> list[NoteMeta]:
        """All vault sources: editable .md notes plus read-only documents
        (PDF, TXT, HTML, DOCX). Documents share the note namespace; when a
        .md and a document share a stem, the markdown note owns the id.
        """
        notes = []
        taken = set()
        for path in sorted(self.root.glob("*.md")):
            stat = path.stat()
            taken.add(path.stem)
            notes.append(
                NoteMeta(
                    id=path.stem,
                    title=self._title_of(path),
                    modified=stat.st_mtime,
                    size=stat.st_size,
                )
            )
        for suffix, (kind, _) in EXTRACTORS.items():
            for path in sorted(self.root.glob(f"*{suffix}")):
                if path.stem in taken or not _ID_RE.match(path.stem):
                    continue
                taken.add(path.stem)
                stat = path.stat()
                notes.append(
                    NoteMeta(
                        id=path.stem,
                        title=path.stem.replace("-", " ").title(),
                        modified=stat.st_mtime,
                        size=stat.st_size,
                        kind=kind,
                    )
                )
        notes.sort(key=lambda n: n.modified, reverse=True)
        return notes

    def kind_of(self, note_id: str) -> str:
        if self._path(note_id).exists():
            return "md"
        found = self._document_path(note_id)
        if found is not None:
            return EXTRACTORS[found.suffix][0]
        raise NoteNotFound(note_id)

    def _document_path(self, note_id: str) -> Path | None:
        for suffix in EXTRACTORS:
            path = self._path(note_id, suffix)
            if path.exists():
                return path
        return None

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
        if path.exists():
            return path.read_text(encoding="utf-8")
        doc_path = self._document_path(note_id)
        if doc_path is not None:
            return self._document_text(doc_path)
        raise NoteNotFound(note_id)

    def _document_text(self, path: Path) -> str:
        """Extracted document text, cached by (path, mtime)."""
        mtime = path.stat().st_mtime
        cached = self._doc_cache.get(str(path))
        if cached and cached[0] == mtime:
            return cached[1]
        _, extractor = EXTRACTORS[path.suffix]
        try:
            text = extractor(path)
        except DocumentError as exc:
            raise VaultError(str(exc))
        self._doc_cache[str(path)] = (mtime, text)
        return text

    def write(self, note_id: str, content: str) -> None:
        if self._document_path(note_id) is not None:
            raise VaultError(f"{note_id} is a document and is read-only")
        self._path(note_id).write_text(content, encoding="utf-8")

    def save_document(self, filename: str, data: bytes) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in EXTRACTORS:
            supported = ", ".join(sorted(EXTRACTORS))
            raise VaultError(f"unsupported document type {suffix or filename!r} — supported: {supported}")
        base = slugify(Path(filename).stem)
        note_id, n = base, 1
        while self._path(note_id).exists() or self._document_path(note_id) is not None:
            n += 1
            note_id = f"{base}-{n}"
        self._path(note_id, suffix).write_bytes(data)
        return note_id

    def create(self, title: str) -> str:
        base = slugify(title)
        note_id, n = base, 1
        while self._path(note_id).exists():
            n += 1
            note_id = f"{base}-{n}"
        self.write(note_id, f"# {title}\n\n")
        return note_id

    def delete(self, note_id: str) -> None:
        for suffix in (".md", *EXTRACTORS):
            path = self._path(note_id, suffix)
            if path.exists():
                path.unlink()
                return
        raise NoteNotFound(note_id)
