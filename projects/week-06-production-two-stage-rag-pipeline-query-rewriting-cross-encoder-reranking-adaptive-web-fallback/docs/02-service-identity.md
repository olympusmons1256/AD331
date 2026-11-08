# Service identity and credential rotation

This fictional Lattice Harbor design uses short-lived workload identities instead of long-lived credentials embedded in container images. A workload obtains a signed identity document from the Dockmaster identity service when it starts. Northgate validates the signature, audience, expiry, and intended tenant scope before forwarding an authenticated request. A valid signature alone does not grant authorization: a separate policy maps the workload identity to allowed actions.

## Trust boundaries

The edge strips external identity headers before adding its own verified principal information. Internal services must accept these headers only from an authenticated gateway connection; otherwise a direct caller could impersonate a principal. Administrative operations require a distinct role and an explicit policy decision. A tenant identifier in the URL or payload is checked against the verified principal, not blindly used as proof of ownership.

## Rotation procedure

Dockmaster publishes a key set with a key identifier for each signing key. During rotation, verifiers accept both the new key and the still-valid old key. Issuers switch to the new key, then operators wait until old tokens and verifier caches have expired before removing the old key. Removing the old key too early breaks legitimate in-flight sessions. If a key is suspected compromised, incident responders may revoke it sooner and require affected workloads to obtain fresh credentials.

## Diagnostics

When requests fail authentication, compare token audience, expiry, key identifier, and verifier clock skew. Do not copy raw tokens into tickets or logs. When authentication succeeds but authorization fails, inspect the principal's action and tenant policy separately; extending token lifetime will not correct a missing authorization rule.