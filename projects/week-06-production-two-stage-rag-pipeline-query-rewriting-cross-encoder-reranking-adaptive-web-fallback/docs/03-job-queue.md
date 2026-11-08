# Crane job queue and delivery

The fictional Crane scheduler accepts work for Lattice Harbor tenants and hands it to workers through the Buoy queue. Each accepted job has a tenant-scoped job ID, a payload reference, and a declared deadline. A successful enqueue acknowledges persistence of the job record, not completion of the work. Clients discover the final state through the job status endpoint.

## Delivery contract

Buoy provides at-least-once delivery: a worker may receive the same job more than once if an acknowledgement is lost or a visibility lease expires. Workers must make externally visible effects idempotent. A worker claims a message for a limited lease, renews the lease while it is active, and acknowledges only after the durable result is committed. A worker that crashes before acknowledgement permits redelivery after the lease expires.

## Retries and poison jobs

Transient failures use bounded exponential backoff with jitter so that many workers do not retry in lockstep. Attempts and the last error category are stored alongside the job. Once the retry budget or deadline is exhausted, the job is moved to a dead-letter queue for inspection. A dead-letter entry is not automatically safe to replay: an operator first checks whether the original side effect may already have succeeded.

## Backlog response

Operators monitor oldest message age as well as queue depth. A small queue with a very old message can indicate a stuck partition; a large queue may simply be a short burst. Scaling workers helps only when the downstream dependency and tenant quotas have spare capacity. If failures originate downstream, more workers can amplify the outage.