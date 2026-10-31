# Service Rollout and Reversal

The Meridian documentation platform is fictional. Percentages, commands, and thresholds on this page are illustrative operational choices, not vendor-specific behavior.

## Define a release unit

A release binds an immutable application image to a configuration version and a compatible database schema range. Record all three before traffic moves. Rebuilding the same source tag later is not a reliable rollback strategy because dependencies or build inputs may have changed. Store an image digest and the migration identifier in the deployment record.

Separate process health from release correctness. A readiness check can confirm that a worker accepts requests, but it cannot prove that document permissions, rendering, or search relevance still work. Add representative synthetic reads and a safe write-and-cleanup check in an isolated workspace.

## Progressive traffic shifting

Start with a small canary, compare it with the existing release, and expand only after enough representative traffic has arrived. A sample progression might be 1%, 10%, 50%, and 100%, with a ten-minute observation window at each step. Low-volume routes may require longer windows or targeted tests; a percentage alone does not establish statistical confidence.

```yaml
illustrative_rollout:
  steps_percent: [1, 10, 50, 100]
  minimum_observation_minutes: 10
  stop_on: [elevated_errors, latency_regression, failed_synthetic]
```

Compare error ratios and latency distributions by route and tenant class, not only global averages. An aggregate can conceal a failure affecting a small administrative endpoint. Account for background job consumers separately: shifting HTTP traffic does not automatically shift queue consumption.

## Schema and compatibility

Use an expand-and-contract sequence for incompatible data changes. First add a nullable field or new table, then deploy code that can read both forms, migrate existing records, and finally remove the old representation after all old binaries are gone. Make backfills restartable and rate-limited. Never assume that reversing an image also reverses data already written by the new version.

Feature flags should have owners, defaults, and removal dates. A flag that changes storage format needs a backward-compatible read path or an explicit point after which rollback requires a data repair plan.

## Abort and recovery

Pause promotion when an alert fires, preserve logs and the release identifier, and route traffic back to the last known-good version. Verify that caches, workers, and schema remain compatible before declaring recovery. If errors persist after rollback, investigate shared dependencies rather than repeatedly toggling releases. Document the decision and follow up on missing tests or misleading health signals.