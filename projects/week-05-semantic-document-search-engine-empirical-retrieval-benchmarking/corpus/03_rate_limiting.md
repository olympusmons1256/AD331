# Fair Request Admission

Meridian is a fictional documentation platform. The policies and configuration below illustrate one possible rate-limiting design rather than a real provider's API.

## Choose the accounting unit

Rate limits protect shared capacity and provide predictable access; they do not replace authentication or capacity planning. Count authenticated requests by principal and workspace, while also applying a coarse network-level ceiling to unauthenticated traffic. A single shared limit for every user behind a corporate proxy can unfairly block an entire organization, so network identity should not be the only dimension.

Different operations consume different resources. A document read may cost one unit, an embedding request ten, and a bulk export fifty. Costs should reflect measured load and be revised when implementation changes. Limit simultaneous long-running exports separately because a request-per-second rule cannot bound their duration.

## Token bucket behavior

A token bucket has a capacity and a refill rate. Admission removes the operation's cost atomically; insufficient tokens result in a rejection. Capacity permits short bursts, while refill controls sustained throughput. For example, a capacity of 120 units and a refill of two units per second allows a brief burst without promising 120 units every second.

```yaml
illustrative_policy:
  scope: workspace_and_principal
  capacity_units: 120
  refill_units_per_second: 2
  export_cost_units: 50
```

Use a monotonic time source within a limiter process. A distributed limiter requires atomic updates at its shared store or a carefully designed reservation scheme. Independent local buckets multiply the effective limit by the number of gateway instances unless each instance receives a bounded allocation.

## Rejection and client behavior

Return a distinct throttling response with a retry delay when the delay can be estimated. The value is guidance, not a promise that capacity will be available at that instant. Clients should add jitter and stop retrying when their overall deadline expires. Never expose another tenant's usage in a rejection message.

An endpoint may have both a per-principal limit and a platform-wide safety limit. Evaluate them in a documented order and avoid charging a user repeatedly for an attempt that was rejected before execution. If accounting spans multiple stores, define whether partial deductions are refunded or accepted as conservative overcounting.

## Degraded operation

When the shared limiter is unreachable, choose fail-open or fail-closed explicitly by route. Public reads might use a small local emergency allowance; expensive writes or exports may be rejected. Alert on limiter errors, unusual rejection ratios, and bucket saturation. Exercise the outage mode under load so the emergency policy does not overload the very services it is intended to protect.