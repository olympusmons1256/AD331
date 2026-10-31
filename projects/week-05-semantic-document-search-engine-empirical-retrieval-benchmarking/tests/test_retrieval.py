from __future__ import annotations

from src.chunking import DocumentChunk
from src.indexer import BM25Indexer, DenseVectorIndexer, HashingEmbedder


def _sample_chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            chunk_id="c1",
            parent_doc="doc",
            content="Use CUSTOM_CONFIG_FLAG_XYZ to enable strict transport retries.",
            metadata={"section_key": "Config Flags"},
        ),
        DocumentChunk(
            chunk_id="c2",
            parent_doc="doc",
            content="Connection pool starvation can be mitigated by bounded queueing and adaptive backpressure.",
            metadata={"section_key": "Pool Reliability"},
        ),
        DocumentChunk(
            chunk_id="c3",
            parent_doc="doc",
            content="Health checks should run before rollouts.",
            metadata={"section_key": "Operations"},
        ),
    ]


def test_exact_match_keyword_retrieval_rank1() -> None:
    chunks = _sample_chunks()
    bm25 = BM25Indexer()
    bm25.index(chunks)

    results, _ = bm25.search("CUSTOM_CONFIG_FLAG_XYZ", k=3)
    assert results[0].chunk_id == "c1"


def test_semantic_paraphrase_dense_retrieval_top_k() -> None:
    chunks = _sample_chunks()
    dense = DenseVectorIndexer(embedder=HashingEmbedder(), use_chroma=False)
    dense.index(chunks)

    query = "How do we stop client channel exhaustion during bursts?"
    results, _ = dense.search(query, k=2)

    assert any(r.chunk_id == "c2" for r in results)
    assert "starvation" not in query.lower()
