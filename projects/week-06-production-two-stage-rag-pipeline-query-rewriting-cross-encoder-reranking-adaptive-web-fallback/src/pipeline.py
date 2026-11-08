"""Two-stage retrieval orchestration with adaptive web fallback and telemetry."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

from .generator import ExtractiveGenerator, validate_answer
from .rewriter import _preserves_query
from .schemas import Document, PipelineResult, RewriteResult, StageTelemetry
from .web_fallback import valid_web_url


class RAGPipeline:
    """Compose injectable components; call run(query) and serialize with to_dict().

    Retriever: search(query, k); reranker: rerank(query, documents, top_k);
    optional rewriter: rewrite(query) -> RewriteResult; optional web search:
    search(query, k); generator: generate(query, documents) -> cited text.
    The threshold is a heuristic on sigmoid-transformed logits, not confidence.
    """

    def __init__(self, retriever: Any, reranker: Any, rewriter: Any = None,
                 web_search: Any = None, generator: Any = None, stage1_k: int = 20,
                 top_k: int = 5, threshold: float = 0.55, web_k: int = 20) -> None:
        if stage1_k <= 0 or top_k <= 0 or web_k <= 0:
            raise ValueError("retrieval and reranking limits must be positive")
        if not math.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        self.retriever, self.reranker, self.rewriter = retriever, reranker, rewriter
        self.web_search = web_search
        self.generator = generator if generator is not None else ExtractiveGenerator()
        self.stage1_k, self.top_k, self.threshold, self.web_k = stage1_k, top_k, threshold, web_k

    def run(self, query: str) -> PipelineResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        telemetry: list[StageTelemetry] = []

        def call(name: str, action: Callable[[], Any]) -> tuple[Any, Exception | None]:
            start = time.perf_counter()
            try:
                result = action()
            except Exception as exc:
                telemetry.append(StageTelemetry(name, "error", (time.perf_counter() - start) * 1000,
                                                f"{type(exc).__name__}: {exc}"))
                return None, exc
            telemetry.append(StageTelemetry(name, "ok", (time.perf_counter() - start) * 1000))
            return result, None

        def skip(name: str, reason: str) -> None:
            telemetry.append(StageTelemetry(name, "skipped", detail=reason))

        rewritten = query
        if self.rewriter is None:
            skip("rewrite", "No rewriter configured")
        else:
            def rewrite() -> RewriteResult:
                result = self.rewriter.rewrite(query)
                if not isinstance(result, RewriteResult) or not isinstance(result.query, str) or not result.query.strip():
                    raise ValueError("rewriter must return a nonblank RewriteResult")
                if not _preserves_query(query, result.query):
                    raise ValueError("rewrite omitted an exact identifier")
                return result
            result, error = call("rewrite", rewrite)
            if error is not None:
                telemetry[-1].status = "fallback"
            else:
                rewritten = result.query
                if result.used_fallback:
                    telemetry[-1].status = "fallback"
                    telemetry[-1].detail = result.reason or "Original query retained"

        def select(documents: Any, source_type: str) -> list[Document]:
            if not isinstance(documents, (list, tuple)):
                raise ValueError("search must return a sequence of Document objects")
            selected = []
            for doc in documents:
                if not isinstance(doc, Document) or doc.source_type != source_type:
                    raise ValueError(f"search returned an invalid {source_type} document")
                if not doc.id or not doc.source or not doc.content.strip():
                    raise ValueError("document id, source, and content are required")
                if source_type == "web" and not valid_web_url(doc.source):
                    raise ValueError("web source must be a valid HTTP(S) URL")
                selected.append(doc)
            return selected

        def rerank(documents: list[Document]) -> list[Document]:
            ranked = self.reranker.rerank(rewritten, documents, top_k=self.top_k)
            if not isinstance(ranked, (list, tuple)) or len(ranked) > self.top_k:
                raise ValueError("reranker returned invalid results")
            originals = {(d.id, d.source, d.content, d.source_type) for d in documents}
            seen = set()
            for doc in ranked:
                if not isinstance(doc, Document) or (doc.id, doc.source, doc.content, doc.source_type) not in originals:
                    raise ValueError("reranker returned a source not present in the input")
                if doc.id in seen:
                    raise ValueError("reranker returned duplicate documents")
                seen.add(doc.id)
                if doc.rerank_score is None or not math.isfinite(doc.rerank_score) or not 0 <= doc.rerank_score <= 1:
                    raise ValueError("reranker returned an invalid score")
            return sorted((doc for doc in ranked if doc.rerank_score >= self.threshold),
                          key=lambda doc: doc.rerank_score, reverse=True)

        local, local_error = call("retrieve", lambda: select(self.retriever.search(rewritten, k=self.stage1_k), "local"))
        candidates: list[Document] = []
        if local_error is not None or not local:
            skip("rerank", "No local candidates")
        else:
            candidates, error = call("rerank", lambda: rerank(local))
            if error is not None:
                candidates = []
            else:
                telemetry[-1].detail = f"{len(candidates)} candidates meet threshold {self.threshold:g}"

        used_web = False
        if candidates:
            skip("web_search", "Local evidence meets threshold")
            skip("web_rerank", "Local evidence meets threshold")
        elif self.web_search is None:
            skip("web_search", "No web search configured")
            skip("web_rerank", "No web candidates")
        else:
            used_web = True
            web, error = call("web_search", lambda: select(self.web_search.search(rewritten, k=self.web_k), "web"))
            if error is not None or not web:
                skip("web_rerank", "No web candidates")
            else:
                candidates, error = call("web_rerank", lambda: rerank(web))
                if error is not None:
                    candidates = []
                else:
                    telemetry[-1].detail = f"{len(candidates)} candidates meet threshold {self.threshold:g}"

        if not candidates:
            skip("generate", "No evidence meets threshold")
            return PipelineResult(query, rewritten, "I cannot answer from the available evidence.",
                                  telemetry=telemetry, abstained=True,
                                  reason="No usable evidence met the relevance threshold", used_web=used_web)

        def generate() -> str:
            answer = self.generator.generate(query, candidates)
            validate_answer(answer, candidates)
            return answer.strip()

        answer, error = call("generate", generate)
        if error is not None:
            return PipelineResult(query, rewritten, "I cannot produce a validated answer from the available evidence.",
                                  sources=candidates, telemetry=telemetry, abstained=True,
                                  reason="Generation or citation validation failed", used_web=used_web)
        return PipelineResult(query, rewritten, answer, sources=candidates, telemetry=telemetry, used_web=used_web)