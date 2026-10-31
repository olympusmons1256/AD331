# Discovering Internal Services

Meridian is a fictional documentation platform; the registry names and timings below are examples for explaining service discovery.

## Service identity and endpoints

The gateway calls logical services such as `document-service` rather than hard-coding worker addresses. A discovery registry maps each service name to currently eligible endpoints and metadata such as zone, protocol version, and readiness state. The logical name is not an authorization credential: clients must still verify the server's transport identity and enforce service-to-service permissions.

An endpoint is eligible only after its process has initialized and passed readiness checks. Liveness answers a different question: whether the process should be restarted. A worker can be alive but temporarily unready while draining connections or waiting for essential state to load. Treating every dependency outage as a liveness failure can cause a restart storm.

## Registration lifecycle

Workers register with a short lease and renew it periodically. For illustration, a lease might last thirty seconds with renewal every ten seconds. These values must be tuned to network variability and the acceptable period during which a dead endpoint remains discoverable. A lease does not prove that a process is healthy at every instant; clients still need connection timeouts and failure handling.

```yaml
service: document-service
endpoint: 10.4.2.18:8443
zone: north-1
lease_seconds: 30
```

The sample is fictional. Registration should be authenticated, and workers should be able to update only their own entries. Validate endpoint addresses and ports so a compromised registrant cannot redirect arbitrary internal traffic.

## Client selection and caching

Clients cache discovery results for a bounded interval and distribute requests across healthy endpoints. Prefer local-zone endpoints when sufficient capacity exists, but allow controlled cross-zone failover. Avoid pinning all requests to the first returned address. When an endpoint repeatedly fails, temporarily reduce its selection probability while continuing occasional probes; permanent exclusion can hide recovery.

When the registry is unavailable, existing clients may use a last-known list for a documented stale period. New clients with no cached list should fail clearly rather than inventing an endpoint. Stale endpoints can still be dangerous after address reuse, which is why transport identity verification matters.

## Draining and troubleshooting

Before termination, mark the worker unready, wait for discovery propagation, then drain in-flight requests up to a deadline. Long streams may require explicit reconnection support. Monitor registration renewal failures, endpoint churn, empty service lists, and the age of cached results. During an incident, compare registry state with actual worker readiness before restarting healthy processes.