from __future__ import annotations

import inspect
import os
import re
import time
from typing import Any, AsyncGenerator, Optional

import tiktoken
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from openai import AsyncOpenAI

from .pricing import calculate_cost_usd
from .schemas import ChunkTelemetry, StreamChunk


class GatewayProviderError(RuntimeError):
    """Base error for gateway-level provider failures."""

    def __init__(self, message: str):
        super().__init__(self._redact(message))
        self.message = self._redact(message)

    @staticmethod
    def _redact(value: str) -> str:
        redacted = value
        for pattern in [
            r"sk-[A-Za-z0-9]+",
            r"OPENAI_API_KEY\s*=.*",
            r"ANTHROPIC_API_KEY\s*=.*",
            r"Bearer\s+[A-Za-z0-9._-]+",
            r"api[_-]?key[:=]\s*['\"]?[^\s'\"]+",
        ]:
            redacted = re.sub(pattern, "[REDACTED]", redacted, flags=re.IGNORECASE)
        return redacted

    def __str__(self) -> str:
        return self.message


class AuthenticationError(GatewayProviderError):
    pass


class RateLimitExceededError(GatewayProviderError):
    pass


class GatewayConnectionError(GatewayProviderError):
    pass


class ModelNotSupportedError(GatewayProviderError):
    pass


class UnifiedLLMGateway:
    PROVIDER_MODELS = {
        "openai": {"gpt-4o", "gpt-4o-mini"},
        "anthropic": {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-3-5-haiku", "claude-3-5-sonnet"},
    }
    ANTHROPIC_MODEL_ALIASES = {
        "claude-3-5-haiku": ["claude-haiku-5-5"],
        "claude-3-5-sonnet": ["claude-sonnet-5-5"],
        "claude-3-5-haiku-latest": ["claude-haiku-5-5"],
        "claude-3-5-sonnet-latest": ["claude-sonnet-5-5"],
        "claude-3-5-haiku-20241022": ["claude-haiku-5-5"],
        "claude-3-5-sonnet-20241022": ["claude-sonnet-5-5"],
        "claude-haiku-5-5": ["claude-haiku-5-5"],
        "claude-sonnet-5-5": ["claude-sonnet-5-5"],
    }

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        *,
        openai_client: Optional[AsyncOpenAI] = None,
        anthropic_client: Optional[AsyncAnthropic] = None,
        anthropic_workspace_id: Optional[str] = None,
    ) -> None:
        load_dotenv()
        self._openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._anthropic_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self._anthropic_workspace_id = anthropic_workspace_id or os.getenv("ANTHROPIC_WORKSPACE_ID")
        self._openai_client = openai_client or (AsyncOpenAI(api_key=self._openai_key) if self._openai_key else None)
        default_headers = None
        if self._anthropic_workspace_id:
            default_headers = {"anthropic-workspace-id": self._anthropic_workspace_id}
        self._anthropic_client = anthropic_client or (
            AsyncAnthropic(api_key=self._anthropic_key, default_headers=default_headers) if self._anthropic_key else None
        )

    @staticmethod
    def resolve_model_name(provider: str, model: str) -> str:
        if provider == "anthropic":
            aliases = UnifiedLLMGateway.ANTHROPIC_MODEL_ALIASES.get(model, [model])
            return aliases[0]
        return model

    def _validate_model(self, provider: str, model: str) -> None:
        allowed = self.PROVIDER_MODELS.get(provider)
        if not allowed:
            raise ModelNotSupportedError(f"Unsupported provider '{provider}'.")
        if provider == "anthropic":
            normalized = self.resolve_model_name(provider, model)
            valid_names = set(self.PROVIDER_MODELS["anthropic"]) | {
                item for values in self.ANTHROPIC_MODEL_ALIASES.values() for item in values
            }
            if model not in valid_names and normalized not in valid_names:
                raise ModelNotSupportedError(f"Model '{model}' is not supported for provider '{provider}'.")
            return
        if model not in allowed:
            raise ModelNotSupportedError(f"Model '{model}' is not supported for provider '{provider}'.")

    def _require_provider_credentials(self, provider: str) -> None:
        if provider == "openai" and not self._openai_key:
            raise AuthenticationError("Missing OPENAI_API_KEY. Set it in the environment or .env file.")
        if provider == "anthropic" and not self._anthropic_key:
            raise AuthenticationError("Missing ANTHROPIC_API_KEY. Set it in the environment or .env file.")

    @staticmethod
    def _redact(value: str) -> str:
        return GatewayProviderError._redact(value)

    @staticmethod
    def count_tokens(text: str, model: str) -> int:
        try:
            if "gpt-4o" in model or "gpt-4" in model:
                encoding = tiktoken.get_encoding("o200k_base")
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return max(1, len(text.split()))

    def count_prompt_tokens(self, prompt: str, model: str) -> int:
        return self.count_tokens(prompt, model)

    def _calculate_telemetry(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_latency_seconds: float,
        ttft_ms: float,
    ) -> ChunkTelemetry:
        total_tokens = prompt_tokens + completion_tokens
        cost = calculate_cost_usd(provider, model, prompt_tokens, completion_tokens)
        tokens_per_second = completion_tokens / total_latency_seconds if total_latency_seconds > 0 else 0.0
        return ChunkTelemetry(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            total_cost_usd=cost,
            ttft_ms=max(ttft_ms, 0.0),
            total_latency_ms=max(total_latency_seconds * 1000.0, 0.0),
            tokens_per_second=max(tokens_per_second, 0.0),
            provider=provider,
            model=model,
        )

    async def _stream_openai(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        self._validate_model("openai", model)
        self._require_provider_credentials("openai")
        if self._openai_client is None:
            raise AuthenticationError("OpenAI client was not initialized with a valid API key.")

        stream_started = time.monotonic()
        first_token_ts: Optional[float] = None
        accumulated_text: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        usage_seen = False

        try:
            response = await self._openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for event in response:
                if getattr(event, "usage", None) is not None:
                    usage = event.usage
                    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                    usage_seen = True
                    continue

                if not getattr(event, "choices", None):
                    continue
                choice = event.choices[0]
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                delta_content = getattr(delta, "content", None)
                if delta_content is None:
                    continue
                content_text = delta_content if isinstance(delta_content, str) else "".join(str(part) for part in delta_content)
                if content_text:
                    if first_token_ts is None:
                        first_token_ts = time.monotonic()
                    accumulated_text.append(content_text)
                    yield StreamChunk(delta_text=content_text, provider="openai", model=model, is_final=False)

            if not usage_seen:
                prompt_tokens = self.count_prompt_tokens(prompt, model)
                completion_tokens = max(1, len("".join(accumulated_text).split()))

            total_latency_secs = max(time.monotonic() - stream_started, 1e-6)
            ttft_ms = 0.0 if first_token_ts is None else (first_token_ts - stream_started) * 1000.0
            telemetry = self._calculate_telemetry(
                provider="openai",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_latency_seconds=total_latency_secs,
                ttft_ms=ttft_ms,
            )
            yield StreamChunk(delta_text="", provider="openai", model=model, is_final=True, telemetry=telemetry)
        except Exception as exc:  # pragma: no cover - centralized error translation
            if "rate limit" in str(exc).lower() or "429" in str(exc):
                raise RateLimitExceededError("OpenAI rate limit exceeded.") from exc
            if "authentication" in str(exc).lower() or "api key" in str(exc).lower():
                raise AuthenticationError("OpenAI authentication failed; verify the API key.") from exc
            if "connection" in str(exc).lower() or "network" in str(exc).lower():
                raise GatewayConnectionError("OpenAI connection error while streaming.") from exc
            raise GatewayProviderError(f"OpenAI provider failure: {exc}") from exc

    async def _stream_anthropic(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        self._validate_model("anthropic", model)
        self._require_provider_credentials("anthropic")
        if self._anthropic_client is None:
            raise AuthenticationError("Anthropic client was not initialized with a valid API key.")

        resolved_model = self.resolve_model_name("anthropic", model)
        if self._anthropic_client is not None:
            try:
                available = self._anthropic_client.models.list()
                for item in getattr(available, "data", []):
                    if item.id and (item.id == resolved_model or item.id.startswith("claude-3-5-haiku") or item.id.startswith("claude-3-5-sonnet")):
                        resolved_model = item.id
                        break
            except Exception:
                pass

        stream_started = time.monotonic()
        first_token_ts: Optional[float] = None
        prompt_tokens = 0
        completion_tokens = 0
        output_text_parts: list[str] = []

        try:
            stream_kwargs = {
                "model": resolved_model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }
            params = inspect.signature(self._anthropic_client.messages.stream).parameters
            if "temperature" in params:
                stream_kwargs["temperature"] = temperature

            stream = self._anthropic_client.messages.stream(**stream_kwargs)
            async with stream as stream_events:
                async for event in stream_events:
                    event_type = getattr(event, "type", "")
                    if event_type == "message_start":
                        prompt_tokens = int(getattr(event.message, "usage", None).input_tokens or 0)
                        continue
                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta is None:
                            continue
                        text = getattr(delta, "text", "") or ""
                        if text:
                            if first_token_ts is None:
                                first_token_ts = time.monotonic()
                            output_text_parts.append(text)
                            yield StreamChunk(delta_text=text, provider="anthropic", model=resolved_model, is_final=False)
                        continue
                    if event_type == "message_delta":
                        delta_usage = getattr(event, "usage", None)
                        if delta_usage is not None:
                            completion_tokens = int(getattr(delta_usage, "output_tokens", 0) or 0)
                        continue
                    if event_type == "message_stop":
                        continue

            if prompt_tokens == 0:
                prompt_tokens = self.count_prompt_tokens(prompt, model)
            if completion_tokens == 0 and output_text_parts:
                completion_tokens = self.count_tokens("".join(output_text_parts), model)

            total_latency_secs = max(time.monotonic() - stream_started, 1e-6)
            ttft_ms = 0.0 if first_token_ts is None else (first_token_ts - stream_started) * 1000.0
            telemetry = self._calculate_telemetry(
                provider="anthropic",
                model=resolved_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_latency_seconds=total_latency_secs,
                ttft_ms=ttft_ms,
            )
            yield StreamChunk(delta_text="", provider="anthropic", model=resolved_model, is_final=True, telemetry=telemetry)
        except Exception as exc:  # pragma: no cover - centralized error translation
            message = str(exc).lower()
            if "rate limit" in message or "429" in str(exc):
                raise RateLimitExceededError("Anthropic rate limit exceeded.") from exc
            if "authentication" in message or "api key" in message:
                raise AuthenticationError("Anthropic authentication failed; verify the API key.") from exc
            if "connection" in message or "network" in message:
                raise GatewayConnectionError("Anthropic connection error while streaming.") from exc
            raise GatewayProviderError(f"Anthropic provider failure: {exc}") from exc

    async def stream(
        self,
        prompt: str,
        model: str,
        provider: str = "openai",
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamChunk, None]:
        provider = provider.lower()
        self._validate_model(provider, model)
        if provider == "openai":
            async for chunk in self._stream_openai(prompt, model=model, temperature=temperature):
                yield chunk
            return
        if provider == "anthropic":
            async for chunk in self._stream_anthropic(prompt, model=model, temperature=temperature):
                yield chunk
            return
        raise ModelNotSupportedError(f"Unsupported provider '{provider}'.")
