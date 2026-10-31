"""Unified search interfaces for semantic benchmark experiments."""

from __future__ import annotations

from pathlib import Path

from .chunking import FixedSizeChunker, StructureAwareChunker, load_markdown_corpus
from .indexer import BM25Indexer, DenseVectorIndexer, Embedder, HashingEmbedder, SearchResult


class SearchWorkbench:
    """Builds chunking/indexing variants and exposes common query methods."""

    def __init__(
        self,
        corpus_dir: Path,
        embedder: Embedder | None = None,
        use_chroma: bool = False,
    ) -> None:
        self.corpus_dir = corpus_dir
        self.embedder = embedder or HashingEmbedder()
        self.use_chroma = use_chroma

        self.bm25 = BM25Indexer()
        self.dense_indices: dict[str, DenseVectorIndexer] = {}

        self._build_indices()

    def _build_indices(self) -> None:
        docs = load_markdown_corpus(self.corpus_dir)
        if not docs:
            raise ValueError(f"No markdown files found in corpus: {self.corpus_dir}")

        bm25_chunks = StructureAwareChunker(max_tokens=1024).chunk_documents(docs)
        self.bm25.index(bm25_chunks)

        chunkers = {
            "dense_256": FixedSizeChunker(chunk_size=256, chunk_overlap=64),
            "dense_1024": FixedSizeChunker(chunk_size=1024, chunk_overlap=128),
            "dense_structure": StructureAwareChunker(max_tokens=1024),
        }

        for name, chunker in chunkers.items():
            chunks = chunker.chunk_documents(docs)
            index = DenseVectorIndexer(
                embedder=self.embedder,
                collection_name=name,
                use_chroma=self.use_chroma,
            )
            index.index(chunks)
            self.dense_indices[name] = index

    def search_bm25(self, query: str, k: int = 5) -> tuple[list[SearchResult], float]:
        return self.bm25.search(query=query, k=k)

    def search_dense(self, query: str, config: str = "dense_structure", k: int = 5) -> tuple[list[SearchResult], float]:
        if config not in self.dense_indices:
            supported = ", ".join(sorted(self.dense_indices.keys()))
            raise KeyError(f"Unknown dense config '{config}'. Supported: {supported}")
        return self.dense_indices[config].search(query=query, k=k)

    def compare(self, query: str, k: int = 5, dense_config: str = "dense_structure") -> dict[str, object]:
        bm25_results, bm25_latency = self.search_bm25(query, k=k)
        dense_results, dense_latency = self.search_dense(query, config=dense_config, k=k)

        return {
            "query": query,
            "k": k,
            "dense_config": dense_config,
            "bm25": {"latency_ms": bm25_latency, "results": bm25_results},
            "dense": {"latency_ms": dense_latency, "results": dense_results},
        }
