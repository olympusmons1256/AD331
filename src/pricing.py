from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

MODEL_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        "claude-sonnet-5-5": {"input": 3.00, "output": 15.00},
        "claude-haiku-5-5": {"input": 0.80, "output": 4.00},
    },
}


def calculate_cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """Return a rounded USD cost with six decimal places for the model usage."""
    if provider not in MODEL_PRICING or model not in MODEL_PRICING[provider]:
        raise ValueError(f"Unsupported model {provider}/{model}")

    pricing = MODEL_PRICING[provider][model]
    usd = (
        Decimal(input_tokens) / Decimal(1_000_000) * Decimal(str(pricing["input"]))
        + Decimal(output_tokens) / Decimal(1_000_000) * Decimal(str(pricing["output"]))
    )
    return float(usd.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
