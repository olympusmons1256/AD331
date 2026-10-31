"""Evaluation harness for retrieval experiments."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import quantiles
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from .indexer import SearchResult
from .search import SearchWorkbench


class EvalQuery(BaseModel):
    query_id: str
    query: str
    query_type: Literal["lexical", "semantic"]
    relevant_section_keys: list[str] = Field(default_factory=list)
    relevant_chunk_ids: list[str] = Field(default_factory=list)


class BenchmarkSummary(BaseModel):
    strategy: str
    k: int
    hit_rate_at_k: float
    recall_at_k: float
    mrr_at_k: float
    latency_p50_ms: float
    latency_p95_ms: float


class RetrievalBenchmarker:
    """Runs benchmark suites against multiple retrieval strategies."""

    def __init__(self, workbench: SearchWorkbench, eval_queries: list[EvalQuery]) -> None:
        self.workbench = workbench
        self.eval_queries = eval_queries

    @staticmethod
    def from_json(workbench: SearchWorkbench, path: Path) -> "RetrievalBenchmarker":
        payload = json.loads(path.read_text(encoding="utf-8"))
        queries = [EvalQuery.model_validate(item) for item in payload]
        return RetrievalBenchmarker(workbench=workbench, eval_queries=queries)

    def run(self, k: int = 5) -> list[BenchmarkSummary]:
        rows: list[BenchmarkSummary] = []

        rows.append(self._evaluate_strategy("bm25", k=k))
        rows.append(self._evaluate_strategy("dense_256", k=k))
        rows.append(self._evaluate_strategy("dense_1024", k=k))
        rows.append(self._evaluate_strategy("dense_structure", k=k))

        return rows

    def run_as_dataframe(self, k: int = 5) -> pd.DataFrame:
        data = [row.model_dump() for row in self.run(k=k)]
        return pd.DataFrame(data)

    def _evaluate_strategy(self, strategy: str, k: int) -> BenchmarkSummary:
        hit_scores: list[float] = []
        recall_scores: list[float] = []
        reciprocal_ranks: list[float] = []
        latencies: list[float] = []

        for eval_query in self.eval_queries:
            if strategy == "bm25":
                retrieved, latency_ms = self.workbench.search_bm25(eval_query.query, k=k)
            else:
                retrieved, latency_ms = self.workbench.search_dense(eval_query.query, config=strategy, k=k)

            hit_scores.append(hit_rate_at_k(retrieved, eval_query, k=k))
            recall_scores.append(recall_at_k(retrieved, eval_query, k=k))
            reciprocal_ranks.append(mrr_at_k(retrieved, eval_query, k=k))
            latencies.append(latency_ms)

        latency_p50, latency_p95 = _percentiles(latencies)

        return BenchmarkSummary(
            strategy=strategy,
            k=k,
            hit_rate_at_k=round(sum(hit_scores) / max(len(hit_scores), 1), 4),
            recall_at_k=round(sum(recall_scores) / max(len(recall_scores), 1), 4),
            mrr_at_k=round(sum(reciprocal_ranks) / max(len(reciprocal_ranks), 1), 4),
            latency_p50_ms=round(latency_p50, 3),
            latency_p95_ms=round(latency_p95, 3),
        )


def _percentiles(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]

    p50, p95 = quantiles(values, n=100, method="inclusive")[49], quantiles(values, n=100, method="inclusive")[94]
    return p50, p95


def is_relevant(result: SearchResult, eval_query: EvalQuery) -> bool:
    section_key = str(result.metadata.get("section_key", ""))
    if section_key and section_key in eval_query.relevant_section_keys:
        return True
    return result.chunk_id in eval_query.relevant_chunk_ids


def hit_rate_at_k(results: list[SearchResult], eval_query: EvalQuery, k: int) -> float:
    top_k = results[:k]
    return 1.0 if any(is_relevant(result, eval_query) for result in top_k) else 0.0


def recall_at_k(results: list[SearchResult], eval_query: EvalQuery, k: int) -> float:
    top_k = results[:k]
    relevant_pool = set(eval_query.relevant_chunk_ids) | set(eval_query.relevant_section_keys)
    if not relevant_pool:
        return 0.0

    hits = 0
    for result in top_k:
        section_key = str(result.metadata.get("section_key", ""))
        if result.chunk_id in relevant_pool or section_key in relevant_pool:
            hits += 1

    return hits / len(relevant_pool)


def mrr_at_k(results: list[SearchResult], eval_query: EvalQuery, k: int) -> float:
    for rank, result in enumerate(results[:k], start=1):
        if is_relevant(result, eval_query):
            return 1.0 / rank
    return 0.0
