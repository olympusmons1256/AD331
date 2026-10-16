# AI Prompt Log and Audit Trail

## Initial prompt used

> You are an expert Python AI Infrastructure Engineer. I need an asynchronous, streaming multi-provider SDK wrapper supporting both OpenAI and Anthropic.
>
> Requirements:
> - Environment: Python 3.11+, typed with Pydantic v2.
> - Architecture: a unified class `UnifiedLLMGateway` with async generator `stream(...)`.
> - Use official async clients (`AsyncOpenAI` and `AsyncAnthropic`).
> - Normalize `StreamChunk` objects with provider-specific event handling.
> - Include pricing tables and telemetry for tokens/sec, TTFT, and cost.
> - Handle auth and rate limit errors with custom exceptions and no raw key leakage.
>
> Provide production-ready code split into `schemas.py`, `pricing.py`, and `gateway.py`.

## Audit findings

### 1. Synchronous client anti-pattern
The initial draft instantiated `openai.OpenAI()` or `anthropic.Anthropic()` inside async methods. This creates blocking I/O on the event loop and defeats streaming responsiveness. The final code uses persistent `AsyncOpenAI` and `AsyncAnthropic` clients stored on the gateway instance.

### 2. OpenAI final usage chunk crash
OpenAI final chunks can contain an empty `choices` list and `choice.delta.content` may be `None`. The initial draft assumed every chunk had a delta with text content. The final code explicitly checks for `choices` and `delta.content is not None` before yielding deltas.

### 3. Anthropic event-type assumptions
Anthropic streams distinct event types (`message_start`, `content_block_delta`, `message_delta`, `message_stop`). The initial draft incorrectly treated all events as content blocks. The final implementation explicitly handles each event type and accumulates input/output token counts correctly.

### 4. TTFT and timing drift
The first pass often measured latency from the API call start instead of the first non-empty token. The final implementation tracks the first real text delta and computes TTFT as `first_token_time - stream_start_time` in milliseconds.

### 5. Floating-point cost precision
The generated draft used naive floating arithmetic for USD totals. The final code uses `Decimal`-based cost estimation and rounds to six decimal places to avoid precision drift.

### 6. Secret redaction
The draft included raw API key substrings in exception messages or logs. The finalized error layer redacts known key patterns such as `sk-...`, `OPENAI_API_KEY=...`, and bearer tokens before they reach outputs.

## Refactoring summary

The final codebase keeps the normalized `StreamChunk` schema, but moves the actual provider logic behind safe async clients, emits telemetry only once on final chunks, and validates environment variables before any network call is attempted.
