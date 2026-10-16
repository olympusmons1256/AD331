from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChunkTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = Field(..., ge=0)
    completion_tokens: int = Field(..., ge=0)
    total_tokens: int = Field(..., ge=0)
    total_cost_usd: float = Field(..., ge=0.0)
    ttft_ms: float = Field(..., ge=0.0)
    total_latency_ms: float = Field(..., ge=0.0)
    tokens_per_second: float = Field(..., ge=0.0)
    provider: str
    model: str


class StreamChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta_text: str = ""
    provider: str
    model: str
    is_final: bool = False
    telemetry: Optional[ChunkTelemetry] = None
