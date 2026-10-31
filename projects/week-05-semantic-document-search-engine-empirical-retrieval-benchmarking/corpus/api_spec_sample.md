# Platform Reliability API Specification

## Deployment Controller

### RollingUpdateDeployment defaults
The `RollingUpdateDeployment` policy supports `maxUnavailable` and `maxSurge`.
By default, `maxUnavailable` is `25%` and `maxSurge` is `25%`.
During heavy traffic windows, keeping `maxUnavailable` too high can reduce live capacity.
For near zero-downtime release windows, operators usually lower `maxUnavailable` and increase `maxSurge`.

### Deployment safety checks
Before rollout, run dependency probes, startup readiness probes, and synthetic checks.
If probes fail for 3 consecutive intervals, abort rollout and freeze writes.

## Connection Management

### Pooled client runtime errors
`ECONNRESET` can occur when stale sockets are reused from a connection pool.
Recommended controls:
- enforce idle timeout eviction
- enable retry with exponential backoff
- cap pending requests per socket

### Preventing socket starvation in pools
Connection pool starvation appears when worker demand exceeds pool throughput.
Mitigations include bounded queueing, adaptive backpressure, and request shedding.
Traffic spikes should trigger dynamic pool expansion with strict upper bounds.

## Configuration Flags

### Rare flags
`CUSTOM_CONFIG_FLAG_XYZ` enables strict payload schema checks.
`ENABLE_HOT_SHARD_MIGRATION` enables online shard transitions for maintenance windows.
`LEGACY_AUTH_BRIDGE_MODE` is deprecated and should remain disabled.

### Runtime tuning
Tune `MAX_RETRY_JITTER_MS`, `CLIENT_POOL_SIZE`, and `WRITE_FLUSH_INTERVAL_MS` as a set.
Changing only one value can produce unstable throughput and queue oscillations.

## API Parameters

### Batch ingest endpoint
`POST /v1/batch/ingest`

Parameters:
- `maxBatchSize` (default: `500`)
- `maxInFlightBatches` (default: `8`)
- `dropMalformedRecords` (default: `false`)

### Search endpoint
`GET /v1/search`

Parameters:
- `query`
- `topK` (default: `5`)
- `retrievalMode` (`bm25`, `dense`, `hybrid`)

## Incident Playbooks

### Zero-downtime maintenance
To preserve user availability during upgrades:
1. Drain traffic gradually.
2. Shift read traffic first.
3. Roll workloads in canary waves.
4. Increase surge capacity before replacing active replicas.

### Network instability response
When client networks degrade:
- reduce concurrency,
- disable long-lived sockets,
- and prefer short retry horizons with jitter.

## Developer Notes

### Markdown examples
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

### Retry pseudocode
```text
if error in [ECONNRESET, ETIMEDOUT]:
    wait = base * (2 ** attempt) + jitter
    retry()
```

## Architecture Reference

### Control plane responsibilities
The control plane coordinates rollout state, safety gates, and policy admission.
It should remain isolated from noisy data-plane traffic.

### Data plane responsibilities
The data plane performs request execution, tokenization, and result serialization.
Do not run heavyweight indexing jobs on latency-sensitive nodes.

## Capacity Engineering

### Handling burst load
Burst traffic can saturate accept queues and worker pools.
Use admission control and adaptive throttling to avoid queue collapse.

### Latency SLO diagnostics
Track p50, p95, and p99 latency by endpoint and request class.
A sudden p95 regression with flat p50 often signals tail retries or lock contention.

## Search Quality Guidance

### Lexical vs semantic retrieval
Lexical retrieval excels for identifiers, flags, and exact parameter names.
Semantic retrieval excels for paraphrased intents and conceptual language.
A hybrid router can choose mode by query class.

### Chunking strategy impact
Fixed token windows are simple but may split context boundaries.
Structure-aware chunking preserves section semantics and code examples.
Empirical benchmark results should guide final strategy selection.
