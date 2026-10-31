# HTTP Retry and Deadline Policy

Meridian is a fictional documentation platform. The timing values below are illustrative and should be selected from measured behavior in a real system.

## Separate attempts from the operation

A request can fail before connecting, during transmission, or after the server commits a change but before the response reaches the client. A timeout therefore does not prove that the server did nothing. Safe reads are generally retryable, while writes require an explicit idempotency contract or another way to establish their outcome. Do not retry validation errors or authentication failures without changing the underlying request or credentials.

Define one end-to-end deadline for the user operation. Every attempt, backoff sleep, DNS lookup, and connection setup consumes that budget. Per-attempt timeouts prevent one slow attempt from monopolizing the entire deadline, but they must never extend the operation beyond its overall limit.

## Backoff and jitter

For transient overload or unavailable upstreams, use exponential backoff with randomized delay and a maximum number of attempts. For example, an initial ceiling of 100 milliseconds, doubled after each failure and capped at one second, spreads clients over time. Full jitter selects a random delay between zero and the current ceiling. Honor a valid server-provided retry delay when it fits inside the remaining deadline.

```text
delay_ceiling = min(100 ms * 2^retry_number, 1000 ms)
sleep = random_between(0, delay_ceiling)
```

These are illustrative values, not a standardized protocol. Limit attempts as well as elapsed time. If the caller has only 50 milliseconds left, a retry requiring a fresh connection is unlikely to be useful.

## Prevent retry amplification

If the gateway, document service, and storage client each make three attempts, one user operation can produce up to 27 downstream attempts. Assign retry responsibility to a specific layer for each failure class, and propagate the remaining deadline. A retry budget can cap additional attempts to a small fraction of normal traffic during an outage. Circuit breakers and admission limits complement this budget but do not make unsafe writes retryable.

For streaming requests, determine whether the body can be replayed and whether any response bytes have already been delivered. Automatic replay of a partially consumed stream can corrupt application semantics.

## Instrumentation and tests

Record original operation count, attempt count, final outcome, and accumulated retry delay separately. Keep high-cardinality request identifiers out of metric labels. Test connection resets, delayed responses after a committed write, overload responses, and exhausted deadlines. Confirm that clients stop promptly on cancellation and that an idempotency key is reused across attempts of the same logical write.