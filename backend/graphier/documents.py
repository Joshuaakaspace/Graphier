"""Text extraction for non-Markdown vault sources.

Every supported format reduces to plain text and then flows through the
identical pipeline as a Markdown note: extraction, domains, evidence,
search, inference, queries. All parsers here are stdlib except pypdf.
"""

from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


class DocumentError(Exception):
    pass


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    try:
        pages = [page.extract_text() or "" for page in PdfReader(path).pages]
    except Exception as exc:
        raise DocumentError(f"could not read PDF {path.name}: {exc}")
    return "\n\n".join(p.strip() for p in pages if p.strip())


def plain_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise DocumentError(f"could not read {path.name}: {exc}")


_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.chunks.append(data)


def html_text(path: Path) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        raise DocumentError(f"could not parse HTML {path.name}: {exc}")
    text = "".join(parser.chunks)
    # Collapse whitespace runs but keep paragraph breaks.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def docx_text(path: Path) -> str:
    # A .docx is a zip; the document body lives in word/document.xml.
    try:
        with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
    except Exception as exc:
        raise DocumentError(f"could not read DOCX {path.name}: {exc}")
    paragraphs = []
    for para in root.iter(f"{{{_DOCX_NS['w']}}}p"):
        runs = [t.text or "" for t in para.iter(f"{{{_DOCX_NS['w']}}}t")]
        joined = "".join(runs).strip()
        if joined:
            paragraphs.append(joined)
    return "\n\n".join(paragraphs)


# extension -> (kind, extractor). Markdown is handled by the vault itself.
EXTRACTORS = {
    ".pdf": ("pdf", pdf_text),
    ".txt": ("txt", plain_text),
    ".html": ("html", html_text),
    ".htm": ("html", html_text),
    ".docx": ("docx", docx_text),
}
