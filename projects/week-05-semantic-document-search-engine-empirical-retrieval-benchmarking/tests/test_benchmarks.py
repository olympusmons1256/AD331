from __future__ import annotations

from src.benchmarker import EvalQuery, hit_rate_at_k, mrr_at_k
from src.indexer import SearchResult


def test_metric_math_hit_rate_and_mrr_with_miss_case() -> None:
    query = EvalQuery(
        query_id="q1",
        query="demo",
        query_type="lexical",
        relevant_section_keys=["target-section"],
    )

    results = [
        SearchResult(chunk_id="a", content="...", score=0.9, parent_doc="doc", metadata={"section_key": "noise"}),
        SearchResult(chunk_id="b", content="...", score=0.8, parent_doc="doc", metadata={"section_key": "target-section"}),
        SearchResult(chunk_id="c", content="...", score=0.7, parent_doc="doc", metadata={"section_key": "other"}),
    ]

    assert hit_rate_at_k(results, query, k=1) == 0.0
    assert hit_rate_at_k(results, query, k=2) == 1.0
    assert mrr_at_k(results, query, k=1) == 0.0
    assert mrr_at_k(results, query, k=2) == 0.5


def test_mrr_returns_zero_when_relevant_outside_top_k() -> None:
    query = EvalQuery(
        query_id="q2",
        query="demo",
        query_type="semantic",
        relevant_chunk_ids=["z"],
    )

    results = [
        SearchResult(chunk_id="a", content="...", score=0.9, parent_doc="doc", metadata={}),
        SearchResult(chunk_id="b", content="...", score=0.8, parent_doc="doc", metadata={}),
        SearchResult(chunk_id="z", content="...", score=0.1, parent_doc="doc", metadata={}),
    ]

    assert mrr_at_k(results, query, k=2) == 0.0
