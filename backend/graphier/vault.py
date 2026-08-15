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
    kind: str = "md"  # "md" (editable note) or "pdf" (read-only document)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


class Vault:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._pdf_cache: dict[str, tuple[float, str]] = {}

    def _path(self, note_id: str, suffix: str = ".md") -> Path:
        # IDs are flat slugs; reject anything that could escape the vault.
        if not _ID_RE.match(note_id):
            raise VaultError(f"invalid note id: {note_id!r}")
        path = (self.root / f"{note_id}{suffix}").resolve()
        if path.parent != self.root:
            raise VaultError(f"invalid note id: {note_id!r}")
        return path

    def list_notes(self) -> list[NoteMeta]:
        """All vault sources: editable .md notes and read-only .pdf documents.

        PDFs share the note namespace; when a .md and .pdf share a stem the
        markdown note owns the id and the PDF is skipped.
        """
        notes = []
        md_stems = set()
        for path in sorted(self.root.glob("*.md")):
            stat = path.stat()
            md_stems.add(path.stem)
            notes.append(
                NoteMeta(
                    id=path.stem,
                    title=self._title_of(path),
                    modified=stat.st_mtime,
                    size=stat.st_size,
                )
            )
        for path in sorted(self.root.glob("*.pdf")):
            if path.stem in md_stems or not _ID_RE.match(path.stem):
                continue
            stat = path.stat()
            notes.append(
                NoteMeta(
                    id=path.stem,
                    title=path.stem.replace("-", " ").title(),
                    modified=stat.st_mtime,
                    size=stat.st_size,
                    kind="pdf",
                )
            )
        notes.sort(key=lambda n: n.modified, reverse=True)
        return notes

    def kind_of(self, note_id: str) -> str:
        if self._path(note_id).exists():
            return "md"
        if self._path(note_id, ".pdf").exists():
            return "pdf"
        raise NoteNotFound(note_id)

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
        pdf_path = self._path(note_id, ".pdf")
        if pdf_path.exists():
            return self._pdf_text(pdf_path)
        raise NoteNotFound(note_id)

    def _pdf_text(self, path: Path) -> str:
        """Extracted PDF text, cached by (path, mtime)."""
        key = (str(path), path.stat().st_mtime)
        cached = self._pdf_cache.get(str(path))
        if cached and cached[0] == key[1]:
            return cached[1]
        from pypdf import PdfReader

        try:
            pages = [page.extract_text() or "" for page in PdfReader(path).pages]
        except Exception as exc:
            raise VaultError(f"could not read PDF {path.name}: {exc}")
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        self._pdf_cache[str(path)] = (key[1], text)
        return text

    def write(self, note_id: str, content: str) -> None:
        if self._path(note_id, ".pdf").exists():
            raise VaultError(f"{note_id} is a PDF document and is read-only")
        self._path(note_id).write_text(content, encoding="utf-8")

    def save_pdf(self, filename: str, data: bytes) -> str:
        base = slugify(Path(filename).stem)
        note_id, n = base, 1
        while self._path(note_id).exists() or self._path(note_id, ".pdf").exists():
            n += 1
            note_id = f"{base}-{n}"
        self._path(note_id, ".pdf").write_bytes(data)
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
        for suffix in (".md", ".pdf"):
            path = self._path(note_id, suffix)
            if path.exists():
                path.unlink()
                return
        raise NoteNotFound(note_id)
