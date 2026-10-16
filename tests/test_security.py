from __future__ import annotations

import asyncio

from src.gateway import AuthenticationError, GatewayProviderError, UnifiedLLMGateway


def test_missing_key_handling_raises_authentication_error(monkeypatch):
    async def check():
        monkeypatch.setenv("OPENAI_API_KEY", "")
        gateway = UnifiedLLMGateway(openai_api_key=None)
        try:
            async for _ in gateway.stream("hello", model="gpt-4o-mini", provider="openai"):
                pass
        except AuthenticationError:
            return
        raise AssertionError("AuthenticationError was not raised for missing OPENAI_API_KEY")

    asyncio.run(check())


def test_secret_redaction_hides_api_key_materials():
    err = GatewayProviderError("Bearer sk-proj-secret-12345 and OPENAI_API_KEY=sk-abc")
    message = str(err)
    assert "sk-proj-secret-12345" not in message
    assert "sk-abc" not in message
    assert "[REDACTED]" in message
