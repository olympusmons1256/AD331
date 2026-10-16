from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from src.gateway import UnifiedLLMGateway

load_dotenv()


app = FastAPI(title="Multi-Provider LLM Gateway")


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Multi-Provider LLM Gateway</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; background: #111827; color: #f9fafb; }
      .container { max-width: 980px; margin: 0 auto; }
      .panel { background: #1f2937; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
      textarea, select, input { width: 100%; box-sizing: border-box; padding: 10px; border-radius: 8px; border: 1px solid #374151; background: #0f172a; color: white; }
      button { background: #2563eb; color: white; border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
      .output { white-space: pre-wrap; min-height: 180px; background: #020817; padding: 12px; border-radius: 8px; }
      .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
      .stat { background: #0f172a; padding: 12px; border-radius: 10px; }
      .label { color: #9ca3af; font-size: 12px; text-transform: uppercase; }
      .value { font-size: 24px; margin-top: 8px; }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Multi-Provider LLM Gateway</h1>
      <div class="panel">
        <label>Provider
          <select id="provider">
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </label>
        <label>Model
          <select id="model">
            <option value="gpt-4o-mini">gpt-4o-mini</option>
            <option value="gpt-4o">gpt-4o</option>
            <option value="claude-haiku-5-5">claude-haiku-5-5</option>
            <option value="claude-sonnet-5-5">claude-sonnet-5-5</option>
            <option value="claude-3-5-haiku">claude-3-5-haiku</option>
            <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
          </select>
        </label>
        <label>Temperature
          <input id="temperature" type="number" min="0" max="2" step="0.1" value="0.7" />
        </label>
        <label>Prompt
          <textarea id="prompt" rows="6">Explain streaming telemetry in simple terms.</textarea>
        </label>
        <button id="run">Run Stream</button>
      </div>
      <div class="panel">
        <div class="output" id="output"></div>
      </div>
      <div class="panel stats" id="stats">
        <div class="stat"><div class="label">TTFT</div><div class="value" id="ttft">--</div></div>
        <div class="stat"><div class="label">Tokens/s</div><div class="value" id="tps">--</div></div>
        <div class="stat"><div class="label">Prompt Tokens</div><div class="value" id="prompt_tokens">--</div></div>
        <div class="stat"><div class="label">Completion Tokens</div><div class="value" id="completion_tokens">--</div></div>
        <div class="stat"><div class="label">Cost</div><div class="value" id="cost">--</div></div>
      </div>
    </div>
    <script>
      document.getElementById('run').addEventListener('click', async () => {
        const prompt = document.getElementById('prompt').value;
        const provider = document.getElementById('provider').value;
        const model = document.getElementById('model').value;
        const temperature = Number(document.getElementById('temperature').value || 0.7);
        const outputEl = document.getElementById('output');
        outputEl.textContent = 'Streaming...';

        const resp = await fetch('/api/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, provider, model, temperature })
        });

        if (!resp.ok) {
          const text = await resp.text();
          outputEl.textContent = `Request failed: ${text}`;
          return;
        }

        const reader = resp.body?.getReader();
        if (!reader) {
          outputEl.textContent = 'Streaming response is unavailable.';
          return;
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split('\\n\\n');
          buffer = parts.pop() || '';
          for (const part of parts) {
            const lines = part.split('\\n');
            let eventName = 'message';
            let payloadText = '';

            for (const line of lines) {
              if (line.startsWith('event:')) {
                eventName = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                payloadText += line.slice(5).trim();
              }
            }

            if (!payloadText) continue;

            try {
              const payload = JSON.parse(payloadText);
              if (eventName === 'error' || payload.error) {
                outputEl.textContent = `Error: ${payload.error || payloadText}`;
                return;
              }
              if (payload.delta_text) {
                outputEl.textContent += payload.delta_text;
              }
              if (payload.telemetry) {
                const t = payload.telemetry;
                document.getElementById('ttft').textContent = `${t.ttft_ms.toFixed(2)} ms`;
                document.getElementById('tps').textContent = t.tokens_per_second.toFixed(2);
                document.getElementById('prompt_tokens').textContent = `${t.prompt_tokens}`;
                document.getElementById('completion_tokens').textContent = `${t.completion_tokens}`;
                document.getElementById('cost').textContent = `$${t.total_cost_usd.toFixed(6)}`;
              }
            } catch (error) {
              console.error('Failed to parse SSE payload', error, payloadText);
            }
          }
        }
      });
    </script>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=HTML_PAGE)


@app.post("/api/stream")
async def stream_api(payload: dict[str, Any]) -> StreamingResponse:
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")

    provider = str(payload.get("provider", "openai"))
    model = str(payload.get("model", "gpt-4o-mini"))
    temperature = float(payload.get("temperature", 0.7))

    async def event_stream():
        gateway = UnifiedLLMGateway()
        try:
            async for chunk in gateway.stream(prompt=prompt, model=model, provider=provider, temperature=temperature):
                payload_json = json.dumps(chunk.model_dump())
                yield f"data: {payload_json}\n\n"
        except Exception as exc:  # pragma: no cover - defensive UI layer
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)
