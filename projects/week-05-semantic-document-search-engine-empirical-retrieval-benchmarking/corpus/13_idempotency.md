# Idempotent Write Requests

Meridian is a fictional documentation platform. The header and storage model below illustrate a possible contract and are not a real vendor API.

## The uncertain outcome problem

A client may submit a document creation request, lose the response, and be unable to tell whether creation succeeded. Blindly sending the request again can create a second document. An idempotency key identifies one logical operation across retries so the server can return the original result instead of repeating the effect.

The client generates a sufficiently unpredictable key and reuses it only for retries of the same operation. The server scopes the key to the authenticated principal or workspace and the operation type. A key is not a credential and must not allow one tenant to retrieve another tenant's response. Authentication and authorization remain mandatory on every attempt.

## Reservation and result storage

```http
POST /v1/documents
Idempotency-Key: 3c42-example-operation
Content-Type: application/json
```

This fictional header demonstrates the idea. Store a canonical request fingerprint, operation state, and final response reference under a unique scoped key. Concurrent requests with the same key must race through an atomic insert or equivalent reservation, not a check followed by an unprotected insert. A request using the same key with a different payload should be rejected rather than silently receiving an unrelated result.

Where possible, commit the reservation, document change, and stored outcome in one database transaction. If an external side effect is involved, use an outbox or a downstream idempotency mechanism; a local database transaction cannot atomically commit a remote email or payment-like action by itself.

## In-progress and expiry behavior

For a duplicate request while the original is running, return a documented in-progress result or wait for a bounded interval. A worker crash can leave an in-progress record behind, so use a recoverable lease and reconcile actual side effects before allowing another worker to continue. Do not simply delete the reservation on timeout when the original operation may still commit.

Choose retention to exceed the supported retry window. For example, a 24-hour record lifetime means a retry after that interval may execute again; clients must understand this limitation. Protect stored responses according to their sensitivity and avoid persisting bearer tokens in request fingerprints.

## Validation and operations

Test simultaneous duplicates, reordered JSON fields, mismatched payloads, server crashes at each commit boundary, and expiry followed by a late retry. Monitor duplicate hits, conflicting reuse, abandoned reservations, and storage growth. Idempotency provides repeatable behavior for a defined operation and retention window; it is not a blanket claim of exactly-once execution across independent systems.