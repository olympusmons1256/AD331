# Observability and incident triage

This page describes an illustrative, fictional Lattice Harbor telemetry design. Services emit structured logs with a request ID, service name, operation, status, and timestamp. Distributed traces link calls across Northgate, Crane, and Lantern. Metrics summarize rates, latency distributions, and resource saturation. The request ID helps join evidence, but it is not an authorization credential.

## Cardinality and privacy

Metrics labels are limited to bounded dimensions such as service, route family, and response class. Tenant IDs, raw URLs, job IDs, and request IDs belong in controlled logs or traces rather than metric labels, where unbounded values would create excessive series. Logs and traces exclude access tokens, secrets, and request bodies by default. Access to detailed diagnostic data should be limited and audited.

## Triage path

Start with user impact: which operations are failing, since when, and for which traffic segment? Compare the gateway error rate with backend error rate and queue age. A gateway rejection without a matching upstream attempt points to admission or routing; successful gateway forwarding with a growing queue suggests a different bottleneck. Use a representative request ID to follow the trace, but do not extrapolate a single trace to the entire fleet.

## Alert design

An alert should identify a symptom and an owner, link to a runbook, and include enough context to distinguish a persistent issue from a brief fluctuation. Dashboards may provide supporting signals without paging anyone. Time windows, service objectives, and alert thresholds require local measurement and review; no numerical reliability target is claimed here.