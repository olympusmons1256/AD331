from __future__ import annotations

from types import SimpleNamespace

import tiktoken

from src.gateway import UnifiedLLMGateway


class DummyOpenAIStream:
    def __init__(self, events):
        self._events = iter(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class DummyAnthropicStream:
    def __init__(self, events):
        self._events = iter(events)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._events)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeOpenAIClient:
    def __init__(self, events):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._events = events

    async def _create(self, **kwargs):
        return DummyOpenAIStream(self._events)


class FakeAnthropicClient:
    def __init__(self, events):
        self.messages = SimpleNamespace(stream=self._stream)
        self._events = events

    def _stream(self, **kwargs):
        return DummyAnthropicStream(self._events)


async def _collect(provider: str, model: str, prompt: str, *, api_key: str, events, client_type):
    gateway = UnifiedLLMGateway(
        openai_api_key=api_key if provider == "openai" else None,
        anthropic_api_key=api_key if provider == "anthropic" else None,
        openai_client=FakeOpenAIClient(events) if client_type == "openai" else None,
        anthropic_client=FakeAnthropicClient(events) if client_type == "anthropic" else None,
    )
    chunks = []
    async for chunk in gateway.stream(prompt=prompt, model=model, provider=provider):
        chunks.append(chunk)
    return chunks


def test_unified_stream_protocol_for_openai_and_anthropic():
    openai_events = [
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello"))]),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=" world"))]),
        SimpleNamespace(choices=[]),
    ]
    anthropic_events = [
        SimpleNamespace(type="message_start", message=SimpleNamespace(usage=SimpleNamespace(input_tokens=11))),
        SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(text="Hello")),
        SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(text=" there")),
        SimpleNamespace(type="message_delta", usage=SimpleNamespace(output_tokens=3)),
        SimpleNamespace(type="message_stop"),
    ]

    async def run():
        openai_chunks = await _collect(
            "openai",
            "gpt-4o-mini",
            "Say hello",
            api_key="sk-test-openai",
            events=openai_events,
            client_type="openai",
        )
        anthropic_chunks = await _collect(
            "anthropic",
            "claude-3-5-haiku",
            "Say hello",
            api_key="sk-ant-test",
            events=anthropic_events,
            client_type="anthropic",
        )
        return openai_chunks, anthropic_chunks

    openai_chunks, anthropic_chunks = __import__("asyncio").run(run())

    openai_text = "".join(chunk.delta_text for chunk in openai_chunks if not chunk.is_final and chunk.delta_text)
    anthropic_text = "".join(chunk.delta_text for chunk in anthropic_chunks if not chunk.is_final and chunk.delta_text)

    assert openai_text == "Hello world"
    assert anthropic_text == "Hello there"
    assert all(chunk.provider in {"openai", "anthropic"} for chunk in openai_chunks + anthropic_chunks)
    assert any(chunk.is_final for chunk in openai_chunks)
    assert any(chunk.is_final for chunk in anthropic_chunks)


def test_token_count_validation_matches_tiktoken():
    async def run():
        prompt = " ".join(["token", "count", "validation", "should", "match", "tiktoken"] * 10)
        gateway = UnifiedLLMGateway(openai_api_key="sk-test-openai")
        gateway._openai_client = FakeOpenAIClient([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]),
            SimpleNamespace(choices=[]),
        ])
        chunks = []
        async for chunk in gateway.stream(prompt=prompt, model="gpt-4o-mini", provider="openai"):
            chunks.append(chunk)
        telemetry = next(chunk.telemetry for chunk in chunks if chunk.is_final)
        expected_tokens = len(tiktoken.get_encoding("o200k_base").encode(prompt))
        assert telemetry.prompt_tokens > 0
        assert abs(telemetry.prompt_tokens - expected_tokens) / expected_tokens <= 0.10

    __import__("asyncio").run(run())


def test_telemetry_sanity_for_final_stream_chunk():
    async def run():
        gateway = UnifiedLLMGateway(openai_api_key="sk-test-openai")
        gateway._openai_client = FakeOpenAIClient([
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Telemetry check"))]),
            SimpleNamespace(choices=[]),
        ])
        chunks = []
        async for chunk in gateway.stream(prompt="Telemetry check", model="gpt-4o-mini", provider="openai"):
            chunks.append(chunk)
        final = next(chunk for chunk in chunks if chunk.is_final)
        telemetry = final.telemetry
        assert telemetry is not None
        assert telemetry.total_cost_usd > 0
        assert telemetry.tokens_per_second > 0
        assert telemetry.ttft_ms > 0
        assert telemetry.total_tokens >= telemetry.prompt_tokens + telemetry.completion_tokens

    __import__("asyncio").run(run())
