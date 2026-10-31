# Connection Pool Capacity

Meridian is a fictional documentation platform. Pool sizes and timeout values on this page are examples, not settings for a specific client library.

## Why pools exist

Opening a network connection can require DNS resolution, a transport handshake, and TLS negotiation. A pool reuses established connections to reduce that overhead and bound concurrent work against a dependency. It also introduces a queue: callers may wait for a free connection even when the dependency itself is healthy. Measure acquisition time separately from request execution time.

For a database pool, a connection may hold server-side resources and session state. Return it promptly after each transaction, and reset or discard it if session state cannot be safely restored. Never hold a connection while waiting for unrelated user input or a slow external API.

## Sizing and acquisition

Start from the dependency's connection budget, then divide it across application instances, background workers, operational access, and a safety margin. For example, a database allowing 400 application connections might reserve 80 for workers and administration, leaving 320 for web instances. With eight instances, a pool ceiling of 40 per instance consumes that remaining budget; autoscaling beyond eight requires a lower ceiling or a larger budget.

```yaml
illustrative_pool:
  max_connections: 24
  acquire_timeout_ms: 200
  idle_timeout_seconds: 60
  max_lifetime_seconds: 1800
```

These values are fictional. Set an acquisition timeout shorter than the operation deadline so callers can fail predictably. A very large pool can worsen contention and memory pressure instead of increasing throughput.

## Stale and multiplexed connections

Idle connections may be closed by a proxy, server, or network device without the client noticing immediately. Validate connections when appropriate, discard broken ones, and retry only if the operation is safe. Maximum lifetime should account for server limits and credential rotation; add jitter so every connection does not expire simultaneously.

HTTP connection counts are not always request-concurrency counts. A multiplexed protocol may carry multiple streams on one connection, subject to peer limits and flow control. Conversely, a long-lived stream can occupy capacity for much longer than a short document read. Use separate pools or concurrency limits when their workloads interfere.

## Troubleshooting saturation

Track active, idle, waiting, and timed-out acquisitions, along with connection creation and closure rates. A growing wait queue with low database CPU may indicate leaked connections or transactions held open across external calls. A full pool with high database latency may be a downstream bottleneck, not evidence that the pool should grow. Load-test failure and recovery, including rolling restarts and credential rotation.