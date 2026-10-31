# Authentication and Workspace Identity

This page describes the fictional Meridian documentation platform; token fields and settings are illustrative rather than real vendor APIs.

## Identity and trust

Meridian distinguishes a human user, an automated service account, and an anonymous visitor. Authentication proves which principal is making a request. Authorization is a separate decision based on workspace membership, document visibility, and the requested action. A valid token for one workspace must not grant access to another merely because a document identifier is guessable.

The identity service signs short-lived access tokens after a user completes an interactive login or an automation client proves possession of a credential. Services validate signatures using published public keys, then check issuer, audience, expiration, and a small permitted clock skew. Treat missing or unknown signing keys as authentication failures; never accept an unsigned token as a fallback.

## Example claims

```json
{
  "iss": "meridian-identity",
  "sub": "user-42",
  "aud": "meridian-docs",
  "exp": 1900000600,
  "session_version": 3
}
```

This example is a fictional claim set. The subject identifies a principal, not the current permissions. Resolve workspace roles from an authorization source or a carefully bounded cache, because membership can change before the token expires. Limit token lifetime according to risk; a ten-minute access token is an example, not a universal recommendation.

## Rotation and revocation

Publish a new verification key before signing tokens with it. Keep the prior public key available until all tokens signed with it have expired, including allowed clock skew. A key identifier selects a candidate key but must not be interpreted as a filesystem path or remote URL. Cache key sets with an expiry, refresh once for an unfamiliar identifier, and rate-limit refreshes to avoid a fetch storm.

For urgent revocation, increment a session version or consult a revocation record. State the maximum propagation delay explicitly: a service caching session status for sixty seconds cannot promise instantaneous logout. Revoke compromised service credentials independently of human sessions and audit changes without recording the secret.

## Failure handling

Reject expired tokens and wrong audiences consistently, without revealing whether a user exists. During identity-provider outages, existing locally verifiable tokens may remain usable only if the authorization and revocation policy permits it. Administrative actions can require a fresh session or stronger verification. Synchronize clocks, alert on signature failures and key-refresh errors, and test key rotation before an emergency forces it.