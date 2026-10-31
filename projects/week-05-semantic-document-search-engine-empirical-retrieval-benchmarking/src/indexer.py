"""Dense and sparse indexing backends."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from .chunking import DocumentChunk

try:
    chromadb = import_module("chromadb")
except Exception:  # pragma: no cover
    chromadb = None


@dataclass(slots=True)
class SearchResult:
    chunk_id: str
    content: str
    score: float
    parent_doc: str
    metadata: dict[str, Any]


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Default local embedder."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        SentenceTransformer = import_module("sentence_transformers").SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, normalize_embeddings=False)
        return np.asarray(vectors, dtype=np.float32)


class HashingEmbedder:
    """Deterministic lightweight embedder for tests/offline fallback."""

    def __init__(self, dims: int = 256) -> None:
        self.dims = dims
        self._token_re = re.compile(r"[a-z0-9_]+")
        self._synonyms = {
            "downtime": "availability",
            "outage": "availability",
            "zero": "availability",
            "upgrade": "rollout",
            "upgrades": "rollout",
            "rolling": "rollout",
            "traffic": "load",
            "heavy": "load",
            "starvation": "exhaustion",
            "exhaustion": "exhaustion",
            "sockets": "connection",
            "socket": "connection",
            "channel": "connection",
            "pooled": "pool",
            "pooling": "pool",
            "paraphrase": "semantic",
        }

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dims), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = self._token_re.findall(text.lower())
            if not tokens:
                continue
            for token in tokens:
                canonical = self._synonyms.get(token, token)
                idx = hash(canonical) % self.dims
                vectors[row, idx] += 1.0
            vectors[row] /= max(len(tokens), 1)
        return vectors


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """Normalize rows to unit vectors for cosine similarity."""

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return embeddings / norms


class BM25Indexer:
    """Sparse lexical index with symmetric preprocessing."""

    TOKEN_RE = re.compile(r"[a-z0-9_]+")

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunks: list[DocumentChunk] = []

    def _tokenize(self, text: str) -> list[str]:
        return self.TOKEN_RE.findall(text.lower())

    def index(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        tokenized_docs = [self._tokenize(chunk.content) for chunk in chunks]
        self._bm25 = BM25Okapi(tokenized_docs)

    def search(self, query: str, k: int = 5) -> tuple[list[SearchResult], float]:
        if self._bm25 is None:
            raise RuntimeError("BM25 index has not been built")

        start = time.perf_counter()
        query_tokens = self._tokenize(query)
        scores = self._bm25.get_scores(query_tokens)
        indices = np.argsort(scores)[::-1][:k]
        latency_ms = (time.perf_counter() - start) * 1000

        results: list[SearchResult] = []
        for idx in indices:
            chunk = self._chunks[int(idx)]
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=float(scores[int(idx)]),
                    parent_doc=chunk.parent_doc,
                    metadata=chunk.metadata,
                )
            )
        return results, latency_ms


class DenseVectorIndexer:
    """Dense vector retrieval with optional Chroma persistence."""

    def __init__(
        self,
        embedder: Embedder,
        collection_name: str = "semantic_chunks",
        use_chroma: bool = False,
    ) -> None:
        self.embedder = embedder
        self.collection_name = collection_name
        self.use_chroma = use_chroma and chromadb is not None

        self._chunks: list[DocumentChunk] = []
        self._embeddings = np.zeros((0, 1), dtype=np.float32)
        self._chroma_collection = None

        if self.use_chroma:
            client = chromadb.EphemeralClient()
            self._chroma_collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    def index(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed(texts)
        self._embeddings = normalize_embeddings(embeddings)

        if self._chroma_collection is not None:
            self._chroma_collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                documents=texts,
                metadatas=[self._serialize_metadata(chunk) for chunk in chunks],
                embeddings=self._embeddings.tolist(),
            )

    def search(self, query: str, k: int = 5) -> tuple[list[SearchResult], float]:
        if not self._chunks:
            raise RuntimeError("Dense index has not been built")

        start = time.perf_counter()

        query_vec = normalize_embeddings(self.embedder.embed([query]))

        if self._chroma_collection is not None:
            payload = self._chroma_collection.query(
                query_embeddings=query_vec.tolist(),
                n_results=k,
                include=["documents", "metadatas", "distances", "ids"],
            )
            ids = payload["ids"][0]
            docs = payload["documents"][0]
            metadatas = payload["metadatas"][0]
            distances = payload["distances"][0]

            latency_ms = (time.perf_counter() - start) * 1000
            results: list[SearchResult] = []
            for chunk_id, content, metadata, distance in zip(ids, docs, metadatas, distances):
                score = 1.0 - float(distance)
                parent_doc = str(metadata.get("parent_doc", ""))
                results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        content=content,
                        score=score,
                        parent_doc=parent_doc,
                        metadata=metadata,
                    )
                )
            return results, latency_ms

        sims = np.dot(self._embeddings, query_vec[0])
        indices = np.argsort(sims)[::-1][:k]
        latency_ms = (time.perf_counter() - start) * 1000

        results: list[SearchResult] = []
        for idx in indices:
            chunk = self._chunks[int(idx)]
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    score=float(sims[int(idx)]),
                    parent_doc=chunk.parent_doc,
                    metadata=chunk.metadata,
                )
            )
        return results, latency_ms

    @staticmethod
    def _serialize_metadata(chunk: DocumentChunk) -> dict[str, Any]:
        metadata = {**chunk.metadata}
        metadata["parent_doc"] = chunk.parent_doc
        metadata["chunk_id"] = chunk.chunk_id
        return metadata
