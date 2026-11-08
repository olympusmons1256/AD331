"""Shared, JSON-serializable data structures for retrieval and responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class Document:
    """A corpus chunk or web snippet; scores are model-specific, not probabilities."""

    id: str
    content: str
    source: str
    source_type: Literal["local", "web"] = "local"
    title: str = ""
    retrieval_score: float | None = None
    rerank_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RewriteResult:
    original: str
    query: str
    used_fallback: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StageTelemetry:
    name: str
    status: Literal["ok", "fallback", "error", "skipped"]
    duration_ms: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PipelineResult:
    query: str
    rewritten_query: str
    answer: str
    sources: list[Document] = field(default_factory=list)
    telemetry: list[StageTelemetry] = field(default_factory=list)
    abstained: bool = False
    reason: str | None = None
    used_web: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)