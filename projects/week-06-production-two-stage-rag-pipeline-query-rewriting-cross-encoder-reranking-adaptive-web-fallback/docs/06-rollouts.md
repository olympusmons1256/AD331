# Deployments and rollback

Lattice Harbor uses a fictional deployment controller named Slipway. A release bundles an immutable application image, a configuration revision, and the schema compatibility range expected by that application. Slipway starts a small canary group before replacing the rest of the fleet. Canary metrics are compared with the current stable group over the same period, because traffic volume and request mix can change during a rollout.

## Stages and gates

The controller first checks that the new instances are ready and can reach required dependencies. It then shifts a limited share of traffic and waits for a review window. Operators examine error ratio, latency, saturation, and business-level failures, not just process health. If the canary fails a gate, traffic returns to the stable group and the candidate is held for investigation. Readiness alone cannot detect a logically incorrect response.

## Data compatibility

Database changes follow an expand-migrate-contract sequence. First add a backward-compatible field, then deploy code that can operate during migration, and only remove the old field after old application versions are no longer running. A rollback is unsafe if the new version has already made an irreversible schema change or written data that the old version cannot read. The release plan must identify such constraints before rollout.

## Practical runbook

Record the image digest, configuration revision, schema state, canary start, and decision. If the rollback gate triggers, preserve a sample of request IDs and relevant telemetry before modifying the environment. Avoid repeatedly switching versions while a database migration is still running; establish the actual data state first.