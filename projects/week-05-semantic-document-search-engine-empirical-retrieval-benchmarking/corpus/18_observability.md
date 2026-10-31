# Observability for Documentation Workflows

Meridian is a fictional documentation platform. Metric names, sampling rates, and thresholds below illustrate a possible design rather than a real monitoring product.

## Signals and questions

Metrics reveal aggregate behavior, logs describe discrete events, and traces connect work across service boundaries. Use them together to answer whether document reads are slow, which dependency contributes latency, and whether a deployment changed the failure rate. A trace is not a complete audit trail if sampling drops requests; security-sensitive actions need their own durable audit records.

Define service-level indicators from user-visible outcomes. For example, measure the fraction of authorized document reads that complete successfully within a chosen latency threshold. State the measurement window, excluded requests, and treatment of client cancellations. An objective should reflect user needs and be reviewed against actual traffic rather than chosen solely because it is easy to meet.

## Instrumentation example

```text
meridian_requests_total{route="document_read", outcome="success"}
meridian_request_duration_seconds{route="document_read"}
meridian_queue_oldest_age_seconds{queue="indexing"}
```

These are fictional metric names. Use bounded labels such as route template and outcome category. Document identifiers, email addresses, raw URLs, and request identifiers create unbounded cardinality and may expose sensitive data. Use histograms or equivalent distributions for latency; averaging per-instance percentiles does not produce a valid global percentile.

## Context and privacy

Generate a request identifier at the trust boundary and propagate trace context through gateway calls, database operations, and queue messages. Validate externally supplied context and avoid trusting it as an identity claim. Asynchronous work should link back to its originating operation without requiring the worker to retain a user's bearer token.

Redact credentials and document contents from routine logs. Restrict access, set retention limits, and consider whether a field remains sensitive even after hashing. Sample traces deliberately: retain representative successes and enough failures for diagnosis, while avoiding a feedback loop that overwhelms the telemetry pipeline during an incident.

## Alerting and failure analysis

Alert on sustained user impact and fast error-budget consumption, supplemented by actionable dependency alerts. A single transient error rarely deserves a page; a growing indexing backlog may matter before users notice stale search results. Each alert should identify an owner, a diagnostic entry point, and an expected response.

Test telemetry failure itself. If collectors are unavailable, applications should continue serving within bounded memory and disk limits rather than block indefinitely. Monitor dropped events and ingestion delay so missing telemetry is not mistaken for a healthy system. Review dashboards and alert noise after incidents.