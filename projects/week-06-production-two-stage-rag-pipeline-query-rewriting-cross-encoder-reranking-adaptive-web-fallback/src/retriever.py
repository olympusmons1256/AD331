"""Persistent Chroma retrieval with deterministic chunk IDs and synchronization."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from .schemas import Document


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _vectors(value: Any, expected: int) -> list[list[float]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    rows = [[float(number) for number in row] for row in value]
    if len(rows) != expected or any(not row or any(not math.isfinite(x) for x in row) for row in rows):
        raise ValueError("embedder returned invalid vectors")
    if rows and any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("embedder returned inconsistent vector dimensions")
    return rows


class SentenceTransformerEmbedder:
    """Lazily load a sentence-transformers model for normalized embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", model: Any = None) -> None:
        self.model_name, self.model = model_name, model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("Install sentence-transformers for dense embeddings") from exc
            self.model = SentenceTransformer(self.model_name)
        return _vectors(self.model.encode(texts, normalize_embeddings=True), len(texts))


class ChromaRetriever:
    """Index a dedicated corpus collection. Call sync() after corpus changes.

    Use a distinct collection for each corpus, chunk configuration and embedding
    model. Inject a collection and embedder to test without external services.
    """

    def __init__(self, corpus_dir: str | Path, persist_dir: str | Path,
                 embedder: Any = None, collection_name: str = "rag_corpus",
                 chunk_size: int = 1200, chunk_overlap: int = 200,
                 collection: Any = None, embedder_id: str | None = None) -> None:
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("require chunk_size > 0 and 0 <= chunk_overlap < chunk_size")
        self.corpus_dir = Path(corpus_dir).resolve()
        self.persist_dir = Path(persist_dir)
        self.embedder = embedder if embedder is not None else SentenceTransformerEmbedder()
        self.chunk_size, self.chunk_overlap = chunk_size, chunk_overlap
        self.collection_name, self.collection = collection_name, collection
        model_id = embedder_id or getattr(self.embedder, "model_name", None)
        if not model_id:
            model_id = f"{type(self.embedder).__module__}.{type(self.embedder).__qualname__}"
        self._fingerprint = _hash(f"{self.corpus_dir}\n{chunk_size}\n{chunk_overlap}\n{model_id}")
        self._client: Any = None

    def _get_collection(self) -> Any:
        if self.collection is None:
            try:
                import chromadb
            except ImportError as exc:
                raise RuntimeError("Install chromadb for persistent retrieval") from exc
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.collection = self._client.get_or_create_collection(
                self.collection_name,
                metadata={"hnsw:space": "cosine", "rag_fingerprint": self._fingerprint},
            )
            metadata = self.collection.metadata or {}
            if metadata.get("rag_fingerprint") != self._fingerprint:
                self.collection = None
                raise ValueError("Collection configuration differs; use a new collection name or rebuild it")
        return self.collection

    def sync(self) -> dict[str, int]:
        """Upsert changed chunks and delete obsolete chunks after successful upserts."""
        if not self.corpus_dir.is_dir():
            raise ValueError(f"Corpus directory does not exist: {self.corpus_dir}")
        chunks: dict[str, tuple[str, dict[str, Any]]] = {}
        for path in sorted(self.corpus_dir.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Symlinks are not supported in corpus: {path}")
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            relative = path.relative_to(self.corpus_dir).as_posix()
            text = path.read_text(encoding="utf-8")
            step = self.chunk_size - self.chunk_overlap
            for index, start in enumerate(range(0, len(text), step)):
                content = text[start:start + self.chunk_size]
                if not content.strip():
                    continue
                chunk_id = _hash(f"{relative}\0{index}")
                chunks[chunk_id] = (content, {"source": relative, "title": path.name,
                                              "content_hash": _hash(content), "chunk_index": index})
                if start + self.chunk_size >= len(text):
                    break
        collection = self._get_collection()
        existing = collection.get(include=["metadatas"])
        previous = {str(i): m or {} for i, m in zip(existing["ids"], existing["metadatas"])}
        changed = [i for i, (_, meta) in chunks.items() if previous.get(i) != meta]
        # Bound both model and Chroma request size; never delete if an upsert fails.
        for start in range(0, len(changed), 128):
            ids = changed[start:start + 128]
            texts = [chunks[i][0] for i in ids]
            embeddings = _vectors(self.embedder.embed(texts), len(texts))
            collection.upsert(ids=ids, documents=texts,
                              metadatas=[chunks[i][1] for i in ids], embeddings=embeddings)
        deleted = sorted(set(previous) - set(chunks))
        for start in range(0, len(deleted), 128):
            collection.delete(ids=deleted[start:start + 128])
        return {"total": len(chunks), "upserted": len(changed), "deleted": len(deleted)}

    def search(self, query: str, k: int = 20) -> list[Document]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if k <= 0:
            raise ValueError("k must be positive")
        collection = self._get_collection()
        count = collection.count()
        if not count:
            return []
        payload = collection.query(query_embeddings=_vectors(self.embedder.embed([query]), 1),
                                   n_results=min(k, count),
                                   include=["documents", "metadatas", "distances"])
        results = []
        for chunk_id, content, metadata, distance in zip(payload["ids"][0], payload["documents"][0],
                                                          payload["metadatas"][0], payload["distances"][0]):
            metadata = metadata or {}
            results.append(Document(id=str(chunk_id), content=content or "", source=str(metadata.get("source", "")),
                                    title=str(metadata.get("title", "")), retrieval_score=1.0 - float(distance),
                                    metadata=dict(metadata)))
        return results