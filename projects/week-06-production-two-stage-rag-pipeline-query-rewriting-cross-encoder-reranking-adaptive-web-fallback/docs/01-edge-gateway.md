# Lattice Harbor edge gateway

Lattice Harbor is a fictional infrastructure platform; all service names, policies, and settings on this page are illustrative. Its edge gateway, Northgate, accepts requests for the harbor's internal scheduling services. A request enters through a public TLS listener, passes authentication and a per-tenant admission check, and is then forwarded to a named backend pool. The gateway adds a request ID if the caller did not provide a valid one; it does not trust a caller-supplied tenant ID until the token has been verified.

## Routing and time budgets

Northgate routes `/v1/jobs` to the Crane scheduler and `/v1/inventory` to the Lantern inventory service. Route rules are deployed as versioned configuration. A candidate configuration is validated before it is activated, and a bad configuration can be rolled back to the last known good version. Each request carries a remaining deadline to the backend rather than receiving a fresh timeout at every hop. This prevents a slow chain of services from consuming more time than the caller agreed to wait.

## Admission and failure

The gateway uses separate token buckets for each tenant and route family. Exhaustion produces a rate-limit response with a retry hint; it is not evidence that the backend is unhealthy. A circuit breaker, by contrast, watches recent upstream failures and temporarily rejects new traffic to a struggling pool. Operators should inspect the route, tenant, request ID, and breaker state together. Retrying every rejected request immediately can make either condition worse.

## Operational check

Before changing a route, compare the proposed backend pool and path prefix against the service catalog. After activation, inspect requests grouped by configuration version and verify that the previous version remains available for rollback. Gateway access logs omit authorization headers and request bodies by default.