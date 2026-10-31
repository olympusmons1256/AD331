# Cache Correctness for Documents

Meridian is a fictional documentation platform. Cache names, expiry periods, and key formats in this page are illustrative design choices.

## Cache boundaries

Meridian can cache rendered public pages at the edge, document metadata in an application cache, and computed search results for a short interval. These layers have different security and freshness requirements. A public page cache must not accidentally store a private response, while an application cache may hold private data only if lookup and access controls preserve tenant isolation.

Include the workspace, document identifier, representation version, and any relevant locale in a document cache key. If a response depends on a principal's permissions, either include an appropriate authorization dimension or cache only the underlying data and perform authorization on every request. Never treat an obscure cache key as an access control mechanism.

## Expiry and invalidation

Time-to-live bounds the age of a cached entry only if the cache actually expires it as designed. For illustration, a rendered public page might live for five minutes while a permission decision lives for thirty seconds. Neither value is inherently correct: select it from the tolerated staleness and the frequency of updates.

```text
document:{workspace_id}:{document_id}:render-v3:{locale}
```

On an edit, publish an invalidation event after the authoritative transaction commits. Consumers should tolerate duplicate events. Event delivery can be delayed or lost, so use expiry or versioned keys as a second bound. A versioned key avoids stale overwrites only if readers obtain the current version from a trustworthy source.

## Stampedes and stale responses

When a popular entry expires, many requests can concurrently rebuild it. Collapse equivalent in-process requests, add randomized expiry, or use a bounded distributed lease. A lease holder that crashes must not prevent refresh forever. If stale-while-revalidate is allowed, specify the maximum stale interval and exclude content whose permissions or legal status require immediate removal.

Negative caching can reduce repeated lookups for nonexistent documents, but a long negative TTL makes a newly created document appear missing. Use a short bounded interval and invalidate the negative entry on creation.

## Measurement and incidents

Measure hit ratio alongside miss latency, stale-serving count, eviction rate, and backend load. A high hit ratio is not useful if cached responses violate permissions. Test cross-tenant keys, simultaneous writes, lost invalidation events, and cache outages. During an outage, apply admission control to protect the underlying database rather than allowing every miss to become an unrestricted backend request.