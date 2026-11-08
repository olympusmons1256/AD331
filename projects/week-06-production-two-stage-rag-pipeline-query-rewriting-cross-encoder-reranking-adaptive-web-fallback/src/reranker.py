"""Cross-encoder reranking with a stable sigmoid over raw logits."""

from __future__ import annotations

from dataclasses import replace
import math
from typing import Any

from .schemas import Document


def sigmoid(logit: float) -> float:
    """Convert a finite logit to a bounded score, not a calibrated probability."""
    if not math.isfinite(logit):
        raise ValueError("reranker returned a non-finite logit")
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp = math.exp(logit)
    return exp / (1.0 + exp)


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", model: Any = None) -> None:
        self.model_name, self.model = model_name, model

    def rerank(self, query: str, documents: list[Document], top_k: int = 5) -> list[Document]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not documents:
            return []
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise RuntimeError("Install sentence-transformers for cross-encoder reranking") from exc
            self.model = CrossEncoder(self.model_name, num_labels=1)
        # Explicit identity activation prevents CrossEncoder's model-dependent default sigmoid.
        try:
            import torch
        except ImportError as exc:
            if type(self.model).__module__.startswith("sentence_transformers"):
                raise RuntimeError("Install torch for cross-encoder reranking") from exc
            activation = lambda x: x
        else:
            activation = torch.nn.Identity()
        values = self.model.predict([(query, d.content) for d in documents], activation_fn=activation)
        if hasattr(values, "tolist"):
            values = values.tolist()
        if not isinstance(values, (list, tuple)):
            values = [values]
        if len(values) != len(documents):
            raise ValueError("reranker returned the wrong number of logits")
        scored = [replace(doc, rerank_score=sigmoid(float(value))) for doc, value in zip(documents, values)]
        return sorted(scored, key=lambda doc: doc.rerank_score, reverse=True)[:top_k]