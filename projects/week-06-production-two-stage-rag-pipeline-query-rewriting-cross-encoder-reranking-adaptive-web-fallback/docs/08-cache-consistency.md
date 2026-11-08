# Cache consistency and invalidation

Lantern's fictional Lattice Harbor cache stores frequently read inventory summaries. A cache entry is keyed by tenant and resource ID; omitting the tenant from the key risks exposing another tenant's data. Entries have a time-to-live, but expiry alone does not guarantee that a reader sees the latest committed change. Sensitive authorization decisions are not cached under the same policy as public summaries.

## Write path

After the primary database commits an inventory update, Lantern publishes an invalidation event through its transactional outbox. The cache consumer removes the affected key. Because event delivery can be delayed or duplicated, consumers handle invalidation idempotently and readers tolerate a bounded period of stale data where the product contract permits it. The time-to-live provides an additional recovery mechanism if an invalidation is missed, not an instantaneous consistency guarantee.

## Stampedes and outages

When a popular entry expires, many concurrent misses can overload the database. Per-key request coalescing allows one fetch to populate the entry while other callers wait, subject to a deadline. Short randomized expiry offsets reduce synchronized refreshes. If the cache is unavailable, the service may bypass it only while the primary has sufficient capacity; otherwise it should shed load rather than send an unbounded flood to storage.

## Troubleshooting

For stale results, compare the database commit, outbox event, consumer progress, cache key, and entry age. A recent cache hit does not demonstrate that invalidation was delivered. For authorization-sensitive operations, consult the authoritative policy source instead of assuming an old summary conveys current permissions.