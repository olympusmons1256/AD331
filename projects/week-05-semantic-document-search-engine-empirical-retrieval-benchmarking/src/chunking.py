"""Chunking strategies for technical documentation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tiktoken
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Normalized chunk model used by all retrieval engines."""

    chunk_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_doc: str


@dataclass(slots=True)
class SourceDocument:
    """Raw source document."""

    doc_id: str
    text: str


class FixedSizeChunker:
    """Token-based fixed window chunker with overlap."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._encoder = tiktoken.get_encoding("cl100k_base")

    def chunk_document(self, doc_id: str, text: str) -> list[DocumentChunk]:
        tokens = self._encoder.encode(text)
        if not tokens:
            return []

        stride = self.chunk_size - self.chunk_overlap
        chunks: list[DocumentChunk] = []

        for start in range(0, len(tokens), stride):
            end = min(start + self.chunk_size, len(tokens))
            token_slice = tokens[start:end]
            content = self._encoder.decode(token_slice).strip()
            if not content:
                continue

            chunk_id = f"{doc_id}::fixed-{self.chunk_size}::{start}-{end}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    content=content,
                    parent_doc=doc_id,
                    metadata={
                        "strategy": "fixed",
                        "chunk_size": self.chunk_size,
                        "chunk_overlap": self.chunk_overlap,
                        "token_start": start,
                        "token_end": end,
                        "token_count": len(token_slice),
                        "section_key": "document",
                    },
                )
            )

            if end >= len(tokens):
                break

        return chunks

    def chunk_documents(self, docs: list[SourceDocument]) -> list[DocumentChunk]:
        all_chunks: list[DocumentChunk] = []
        for doc in docs:
            all_chunks.extend(self.chunk_document(doc.doc_id, doc.text))
        return all_chunks


class StructureAwareChunker:
    """Header-aware markdown splitter preserving fenced code blocks."""

    HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    def __init__(self, max_tokens: int = 1024) -> None:
        self.max_tokens = max_tokens
        self._encoder = tiktoken.get_encoding("cl100k_base")

    def chunk_document(self, doc_id: str, text: str) -> list[DocumentChunk]:
        lines = text.splitlines()
        sections = self._extract_sections(lines)

        chunks: list[DocumentChunk] = []
        for section in sections:
            section_text = "\n".join(section.lines).strip()
            if not section_text:
                continue

            token_count = len(self._encoder.encode(section_text))
            sub_parts = [section_text]
            if token_count > self.max_tokens:
                sub_parts = self._split_large_section(section_text)

            for idx, part in enumerate(sub_parts):
                digest = hashlib.md5(part.encode("utf-8")).hexdigest()[:10]
                section_key = "/".join(section.headers) if section.headers else "root"
                chunk_id = f"{doc_id}::struct::{section.start_line}-{section.end_line}::{idx}::{digest}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        content=part,
                        parent_doc=doc_id,
                        metadata={
                            "strategy": "structure-aware",
                            "header_path": section.headers,
                            "section_key": section_key,
                            "line_start": section.start_line,
                            "line_end": section.end_line,
                            "subpart_index": idx,
                            "token_count": len(self._encoder.encode(part)),
                        },
                    )
                )

        return chunks

    def chunk_documents(self, docs: list[SourceDocument]) -> list[DocumentChunk]:
        all_chunks: list[DocumentChunk] = []
        for doc in docs:
            all_chunks.extend(self.chunk_document(doc.doc_id, doc.text))
        return all_chunks

    def _split_large_section(self, text: str) -> list[str]:
        tokens = self._encoder.encode(text)
        if len(tokens) <= self.max_tokens:
            return [text]

        parts: list[str] = []
        start = 0
        while start < len(tokens):
            end = min(start + self.max_tokens, len(tokens))
            part = self._encoder.decode(tokens[start:end]).strip()
            if part:
                parts.append(part)
            start = end
        return parts

    def _extract_sections(self, lines: list[str]) -> list["_Section"]:
        sections: list[_Section] = []
        active_lines: list[str] = []
        active_start = 1
        headers: list[str] = []
        in_code_fence = False

        def flush(end_line: int) -> None:
            nonlocal active_lines, active_start
            body = "\n".join(active_lines).strip()
            if body:
                sections.append(
                    _Section(
                        headers=headers.copy(),
                        lines=active_lines.copy(),
                        start_line=active_start,
                        end_line=end_line,
                    )
                )
            active_lines = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            if stripped.startswith("```"):
                in_code_fence = not in_code_fence

            header_match = self.HEADER_RE.match(line)
            if header_match and not in_code_fence:
                flush(idx - 1)
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                headers = headers[: level - 1]
                headers.append(title)
                active_start = idx
                active_lines = [line]
                continue

            if not active_lines:
                active_start = idx
            active_lines.append(line)

        flush(len(lines))
        return sections


@dataclass(slots=True)
class _Section:
    headers: list[str]
    lines: list[str]
    start_line: int
    end_line: int


def load_markdown_corpus(corpus_dir: Path) -> list[SourceDocument]:
    """Load markdown files as source documents."""

    docs: list[SourceDocument] = []
    for path in sorted(corpus_dir.glob("*.md")):
        docs.append(SourceDocument(doc_id=path.stem, text=path.read_text(encoding="utf-8")))
    return docs
