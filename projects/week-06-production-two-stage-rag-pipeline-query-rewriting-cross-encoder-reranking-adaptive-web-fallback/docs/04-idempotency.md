# Idempotency at the scheduling boundary

Lattice Harbor is fictional. In this example, a client creating a Crane job sends an `Idempotency-Key` scoped to its tenant. Crane stores the key, a hash of the normalized request, and the resulting job ID. A retry with the same key and the same request returns the original job ID rather than creating a second job. A retry with the same key but a different payload is rejected as a conflict.

## Atomicity

The reservation of the idempotency key and creation of the job record happen in the same database transaction. If the transaction rolls back, neither is visible. A unique constraint on tenant and key resolves concurrent submissions; the losing request reads the committed record instead of independently scheduling work. The queue notification is written to an outbox in the transaction and published asynchronously, avoiding a gap between database commit and message publication.

## Expiry and limits

The key record is retained for a documented retry window; after expiry the same key might create a new job. Clients must not assume permanent deduplication. The request hash excludes fields that do not alter the operation, such as a transport request ID, but includes fields that change the job's intended effects. Both normalization and retention policy are part of the API contract and should change only with care.

## Incident check

When investigating duplicate side effects, compare tenant, key, job ID, outbox records, and worker execution history. A unique job record does not automatically make a downstream payment or notification idempotent. Each external effect needs its own durable deduplication boundary or a provider-supported idempotency key.