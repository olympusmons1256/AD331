# SQL Transactions for Document Changes

Meridian is a fictional documentation platform. The SQL examples show general relational concepts; exact syntax and isolation behavior vary by database engine.

## Define the invariant

When a document is edited, Meridian must store the new revision and update the document's current revision together. A transaction makes these database changes atomic: either both commit or neither does. It does not automatically include a search index update or a message sent to another system. Record an outbox event in the same transaction when those systems must eventually observe the change.

Keep the transaction short. Parse and validate the incoming content before opening it where possible, then perform only the necessary reads and writes. Waiting for an external model, sending an email, or rendering a large page while holding locks increases contention and makes failure recovery harder.

## Optimistic concurrency example

```sql
BEGIN;
UPDATE documents
SET current_revision = current_revision + 1
WHERE id = :id AND current_revision = :expected_revision;
-- Insert the revision and outbox event only if one row was updated.
COMMIT;
```

This is illustrative pseudocode: parameter binding and affected-row inspection depend on the driver. If the update affects zero rows, distinguish a missing document from a revision conflict without leaking access-controlled existence. Roll back instead of inserting a revision. The application must enforce workspace authorization before and during the update as appropriate to its data model.

## Isolation and retries

Isolation levels control which concurrent changes a transaction can observe, but their precise guarantees differ across engines. A read-then-write sequence can still violate an invariant if two transactions make decisions from compatible-looking snapshots. Use constraints, explicit locking, conditional updates, or an isolation level that actually protects the invariant, and verify behavior against the chosen engine.

Deadlocks and serialization failures are possible under legitimate concurrency. Retry the entire transaction with bounded jitter when the database reports a retryable condition. Ensure the transaction body has no irreversible external side effects. An ambiguous commit response requires reconciliation or an idempotency key; assuming rollback may duplicate a completed write.

## Operational safeguards

Set transaction and statement timeouts appropriate to the workload. Monitor lock wait time, long-running transactions, rollback rate, and replication lag. Long snapshots can prevent cleanup of old row versions in some databases. Test concurrent edits, process termination before commit, constraint violations, and database failover. Backups and replication do not replace application-level validation of transactional invariants.