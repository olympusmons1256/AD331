"""Query rewriting with a conservative exact-identifier safeguard."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .schemas import RewriteResult


def _preserves_query(original: str, rewritten: str) -> bool:
    # Identifiers can look like ordinary words; preserve all original tokens.
    tokens = Counter(re.findall(r"\S+", rewritten))
    original_tokens = Counter(re.findall(r"\S+", original))
    quoted = {m.group(2) for m in re.finditer(r"(['\"`])(.+?)\1", original) if m.group(2).strip()}
    return all(tokens[token] >= count for token, count in original_tokens.items()) and all(
        phrase in rewritten for phrase in quoted
    )


class OpenAIQueryRewriter:
    """Rewrite through an OpenAI-compatible client; return the original on failure.

    The client can be injected and must expose chat.completions.create. A request
    timeout is passed to the SDK; timeout enforcement depends on that client.
    """

    def __init__(self, model: str = "gpt-4o-mini", timeout: float = 10.0, client: Any = None) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.model, self.timeout, self.client = model, timeout, client

    def rewrite(self, query: str) -> RewriteResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        try:
            if self.client is None:
                try:
                    from openai import OpenAI
                except ImportError as exc:
                    raise RuntimeError("Install openai to use OpenAIQueryRewriter") from exc
                self.client = OpenAI()
            response = self.client.chat.completions.create(
                model=self.model, timeout=self.timeout, temperature=0,
                messages=[
                    {"role": "system", "content": "Rewrite the user's search query for retrieval by adding useful context. Preserve every original whitespace-delimited token, including punctuation and capitalization, and preserve quoted phrases verbatim. Return only the rewritten query."},
                    {"role": "user", "content": query},
                ],
            )
            rewritten = response.choices[0].message.content
            if not isinstance(rewritten, str) or not rewritten.strip():
                raise ValueError("empty rewrite")
            rewritten = rewritten.strip()
            if not _preserves_query(query, rewritten):
                raise ValueError("rewrite omitted an exact identifier")
            return RewriteResult(query, rewritten)
        except Exception as exc:
            return RewriteResult(query, query, True, f"{type(exc).__name__}: {exc}")