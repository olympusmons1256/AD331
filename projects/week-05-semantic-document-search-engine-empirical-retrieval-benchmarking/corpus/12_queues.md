# Asynchronous Work Queues

Meridian is a fictional documentation platform. The queue names and timeouts in this design are illustrative and do not imply a particular message broker.

## Publishing durable work

Meridian uses background jobs for document indexing, export generation, and notification delivery. An HTTP response can acknowledge that work was accepted without claiming that the work has completed. Store an operation identifier and expose a status that distinguishes queued, running, completed, and failed states.

Publishing directly after a database commit creates a gap: the process may crash after saving a document but before sending its indexing message. An outbox table written in the same transaction as the document change closes that gap. A separate publisher sends pending outbox entries and marks them delivered. Because publishing and marking can still be interrupted, consumers must tolerate duplicate messages.

## Delivery and acknowledgment

Assume at-least-once delivery unless the complete system proves a stronger end-to-end guarantee. A worker claims a message, performs the task, persists its outcome, and only then acknowledges it. If the worker crashes before acknowledgment, the message can return. For an indexing task, processing the same document version twice should converge on the same result rather than creating duplicate records.

```yaml
illustrative_queue:
  name: document-indexing
  visibility_timeout_seconds: 120
  maximum_attempts: 5
  dead_letter_destination: indexing-failures
```

The visibility timeout must exceed normal processing time or be renewed while a healthy worker runs. An excessively long timeout delays recovery after a crash. Neither setting eliminates duplicates, particularly when a worker finishes just as its lease expires.

## Ordering and poison messages

Do not assume global ordering across consumers. If document updates must be applied in order, partition by document identifier and include a monotonically increasing version. A consumer can discard an older update after confirming the newer version is already indexed. Events that trigger irreversible side effects require a more careful sequence and deduplication contract.

After bounded retries, move persistently failing work to a dead-letter destination with an error category and attempt history. Keep secrets and full sensitive documents out of diagnostic payloads. Replay should be explicit, auditable, and safe against already completed work.

## Capacity and monitoring

Track queue depth, oldest-message age, processing duration, retry rate, and dead-letter growth. Queue depth alone can be misleading when messages have very different costs. Apply producer backpressure or reduce nonessential work when backlog age breaches the service objective. Test worker termination, duplicate delivery, broker unavailability, and recovery after an extended consumer outage.