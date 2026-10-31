# Partitioning Document Data

Meridian is a fictional documentation platform. The shard counts and routing examples below are illustrative and are not a prescription for a particular database.

## Choosing a partition key

Sharding distributes data and load across independent storage partitions. Meridian can route a workspace to a shard so most document reads, edits, and permission checks remain local. The choice reduces cross-shard operations but makes an unusually large workspace a possible hotspot. Hashing individual document identifiers spreads writes more evenly, yet can make workspace-wide queries and membership checks expensive.

Choose the key from measured access patterns and tenant isolation needs, not only from row counts. Every request should carry a validated workspace identifier, and the router must derive the shard from trusted metadata rather than accepting a client-provided shard number. A routing mistake can become a security boundary failure as well as an availability problem.

## Routing and virtual buckets

```text
bucket = stable_hash(workspace_id) mod 256
shard = routing_table[bucket]
```

This fictional mapping separates a stable set of virtual buckets from the physical shard count. Moving a bucket changes a routing-table entry rather than rehashing every workspace. The hash algorithm and input encoding must be stable across languages and releases. Keep the routing table versioned, replicated, and cached with a bounded lifetime.

## Moving data safely

To move a bucket, copy a consistent snapshot to the destination, capture subsequent changes, and verify that the destination has caught up. Fence or briefly pause writes at cutover, update the authoritative routing table, and reject stale writers using a routing epoch or equivalent guard. Compare counts and representative checksums before retiring the source. Keep a rollback window, but define how writes accepted at the destination will be reconciled if traffic moves back.

Cross-shard transactions are not automatically atomic. Prefer workflows that keep invariants within one shard, or explicitly design a saga with compensating actions and visible intermediate states. Aggregated reports can read asynchronously replicated data when the business accepts lag; they should not pretend to be a globally consistent snapshot.

## Detecting imbalance

Monitor storage, request rate, latency, and queue depth per shard and bucket. A shard with modest storage can still be hot because of a single heavily queried workspace. Test routing-table unavailability, stale caches, partial migrations, and destination failure. Maintain capacity headroom so moving a busy bucket does not overload its new neighbors during recovery.