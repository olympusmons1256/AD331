"""Live web search adapters; never invent citations when search fails."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit

from .schemas import Document


def valid_web_url(url: str) -> bool:
    """Accept only absolute HTTP(S) URLs without credentials or whitespace."""
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 for c in url):
        return False
    try:
        parsed = urlsplit(url)
        return bool(parsed.scheme.lower() in {"http", "https"} and parsed.hostname
                    and parsed.username is None and parsed.password is None
                    and parsed.port != 0 and "\\" not in parsed.netloc)
    except ValueError:
        return False


class WebSearch:
    """Tavily or DuckDuckGo search with an injectable provider client.

    Tavily clients expose search(query=..., max_results=...); DuckDuckGo clients
    expose text(query, max_results=...). Search result snippets remain untrusted.
    """

    def __init__(self, provider: str = "tavily", client: Any = None, timeout: float = 10.0) -> None:
        if provider not in {"tavily", "duckduckgo"}:
            raise ValueError("provider must be 'tavily' or 'duckduckgo'")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.provider, self.client, self.timeout = provider, client, timeout

    def search(self, query: str, k: int = 5) -> list[Document]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must not be blank")
        if k <= 0:
            raise ValueError("k must be positive")
        if self.client is None:
            if self.provider == "tavily":
                try:
                    from tavily import TavilyClient
                except ImportError as exc:
                    raise RuntimeError("Install tavily-python and configure TAVILY_API_KEY for Tavily search") from exc
                import os
                key = os.getenv("TAVILY_API_KEY")
                if not key:
                    raise RuntimeError("TAVILY_API_KEY is required for Tavily search")
                self.client = TavilyClient(api_key=key)
            else:
                try:
                    from ddgs import DDGS
                except ImportError:
                    try:
                        from duckduckgo_search import DDGS
                    except ImportError as exc:
                        raise RuntimeError("Install ddgs (or duckduckgo-search) for DuckDuckGo search") from exc
                self.client = DDGS(timeout=self.timeout)
        try:
            if self.provider == "tavily":
                # Tavily SDK search supports timeout; injected clients follow the same contract.
                response = self.client.search(query=query, max_results=k, timeout=self.timeout)
                entries = response["results"]
            else:
                entries = self.client.text(query, max_results=k)
            documents, seen = [], set()
            for entry in entries:
                url = entry.get("url") or entry.get("href") or ""
                content = entry.get("content") or entry.get("body") or ""
                if not valid_web_url(url) or not isinstance(content, str) or not content.strip() or url in seen:
                    continue
                seen.add(url)
                documents.append(Document(id="web-" + hashlib.sha256(url.encode()).hexdigest(),
                                          content=content.strip(), source=url, source_type="web",
                                          title=str(entry.get("title") or ""),
                                          metadata={"provider": self.provider}))
                if len(documents) == k:
                    break
            return documents
        except Exception as exc:
            raise RuntimeError(f"{self.provider} search failed: {type(exc).__name__}: {exc}") from exc