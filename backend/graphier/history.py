"""Time-travel: the vault's history through git.

The vault is plain files, so history is just git. Snapshots are commits;
replaying the graph at any snapshot means reading the files as they were
and running the same deterministic pipeline — extraction is cached by
content hash, so unchanged notes cost nothing.
"""

from __future__ import annotations

import subprocess
from typing import Any

from .extraction import ExtractionService
from .graph import build_graph
from .vault import Vault


class HistoryError(Exception):
    pass


class VaultHistory:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.root = vault.root

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise HistoryError(result.stderr.strip() or f"git {args[0]} failed")
        return result

    def _ensure_repo(self) -> None:
        if self._git("rev-parse", "--git-dir", check=False).returncode != 0:
            self._git("init", "-q")
            self._git("config", "user.email", "graphier@localhost")
            self._git("config", "user.name", "Graphier")

    def snapshot(self, message: str = "snapshot") -> dict[str, Any]:
        self._ensure_repo()
        self._git("add", "-A")
        commit = self._git("commit", "-q", "-m", message or "snapshot", check=False)
        if commit.returncode != 0:
            if "nothing to commit" in (commit.stdout + commit.stderr):
                return {"created": False, "reason": "nothing changed since last snapshot"}
            raise HistoryError(commit.stderr.strip())
        sha = self._git("rev-parse", "--short", "HEAD").stdout.strip()
        return {"created": True, "sha": sha}

    def list_snapshots(self) -> list[dict[str, Any]]:
        self._ensure_repo()
        log = self._git(
            "log", "--pretty=format:%h%x00%ct%x00%s", check=False
        )
        if log.returncode != 0:  # no commits yet
            return []
        snapshots = []
        for line in log.stdout.splitlines():
            sha, timestamp, message = line.split("\x00", 2)
            snapshots.append({"sha": sha, "timestamp": int(timestamp), "message": message})
        return snapshots

    def notes_at(self, sha: str) -> dict[str, str]:
        """note_id -> content as of the given snapshot."""
        if not sha.replace("-", "").isalnum():
            raise HistoryError(f"invalid ref: {sha!r}")
        listing = self._git("ls-tree", "-r", "--name-only", sha)
        notes = {}
        for name in listing.stdout.splitlines():
            if name.endswith(".md") and "/" not in name:
                content = self._git("show", f"{sha}:{name}").stdout
                notes[name[:-3]] = content
        return notes


class _FrozenVault:
    """Vault-shaped view over a historical snapshot, enough for build_graph."""

    def __init__(self, notes: dict[str, str], root):
        self._notes = notes
        self.root = root

    def list_notes(self):
        from .vault import NoteMeta

        metas = []
        for note_id, content in sorted(self._notes.items()):
            title = next(
                (line[2:].strip() for line in content.splitlines() if line.startswith("# ")),
                note_id.replace("-", " ").title(),
            )
            metas.append(NoteMeta(id=note_id, title=title, modified=0.0, size=len(content)))
        return metas

    def read(self, note_id: str) -> str:
        return self._notes[note_id]


def graph_at(history: VaultHistory, extractor: ExtractionService, sha: str) -> dict[str, Any]:
    frozen = _FrozenVault(history.notes_at(sha), history.root)
    return build_graph(frozen, extractor)  # type: ignore[arg-type]
