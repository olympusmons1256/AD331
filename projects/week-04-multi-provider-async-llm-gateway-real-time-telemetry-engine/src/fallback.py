from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import json_repair  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    json_repair = None


DLQ_PATH = Path(__file__).resolve().parent.parent / "dlq" / "failed_extractions.jsonl"


def repair_malformed_json(raw_json: str) -> dict[str, Any]:
    """Attempt to repair malformed JSON and return a Python dict if possible."""
    if not raw_json or not raw_json.strip():
        return {}

    candidate = raw_json.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`\n ")

    if json_repair is not None:
        try:
            repaired = json_repair.repair(candidate)
            if isinstance(repaired, dict):
                return repaired
        except Exception:
            pass

    try:
        return json.loads(candidate)
    except Exception:
        return {}


def route_to_dlq(payload: dict[str, Any] | str, reason: str) -> Path:
    """Persist an irrecoverable extraction payload to a dead-letter queue."""
    DLQ_PATH.parent.mkdir(parents=True, exist_ok=True)

    item = {
        "reason": reason,
        "payload": payload if isinstance(payload, dict) else {"raw": payload},
    }
    with DLQ_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, default=str) + "\n")
    return DLQ_PATH
