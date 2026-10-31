# Relational Index Design

Meridian is a fictional documentation platform. The schema and SQL below are illustrative; optimizer behavior and index features depend on the chosen database.

## Start with the query

An index trades extra storage and write work for faster access to selected rows. Meridian frequently lists a workspace's published documents in descending update order. An index beginning with the workspace and publication state, followed by the update timestamp, can support that access pattern more effectively than separate indexes on unrelated columns. Confirm this with the actual query plan and representative data rather than assuming an index will be used.

```sql
CREATE INDEX documents_workspace_status_updated
ON documents (workspace_id, status, updated_at DESC);
```

This example is fictional. Equality predicates on leading columns often narrow a composite index before an ordering or range condition, but engine-specific rules, collation, and query shape matter. A query filtering only on the timestamp may not benefit from this index as much as expected.

## Selectivity and pagination

An index on a low-cardinality field such as a boolean publication flag may be unattractive when most rows have the same value. Combining it with a selective workspace identifier can change the calculation. Inspect estimates and actual row counts; stale statistics or skewed tenants can lead the optimizer to choose a poor plan.

For stable pagination, order by a deterministic tie-breaker such as document identifier after the timestamp. A cursor can carry the last observed timestamp and identifier, allowing the next page to seek beyond that pair. Offset pagination becomes increasingly expensive at deep pages and can skip or repeat rows when concurrent edits change ordering. Even cursor pagination needs a defined consistency model if users expect an immutable snapshot.

## Costs and maintenance

Each additional index consumes disk and can slow inserts, updates, and deletes. An index covering more selected columns may reduce table lookups but increase maintenance cost. Measure both read improvements and write regressions. Create large indexes using an engine-supported online method when available, and understand any locking or replication implications before deployment.

Unique indexes can enforce invariants such as a workspace-local document slug, but null handling and case sensitivity vary. Normalize values deliberately and test collisions under concurrent writes. Do not rely on an application-side existence check as the only uniqueness protection.

## Troubleshooting

Collect slow query samples without recording sensitive document text. Compare execution plans before and after schema or data-distribution changes, and monitor index size, write latency, and unused indexes over a meaningful interval. Before removing an apparently unused index, account for infrequent administrative queries and constraint enforcement. Maintain a rollback plan for index changes that unexpectedly degrade production workloads.