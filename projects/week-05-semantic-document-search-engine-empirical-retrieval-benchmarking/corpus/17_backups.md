# Backup and Restore Strategy

Meridian is a fictional documentation platform. The schedules and recovery targets here are illustrative examples, not guarantees provided by a vendor.

## Define recoverable state

A complete recovery may require relational data, uploaded attachments, configuration, encryption keys, and enough metadata to rebuild the search index. Listing only the primary database is insufficient if document bodies live in object storage or if the restored service cannot decrypt them. Classify each component as authoritative, reproducible, or ephemeral, and document dependencies between them.

Recovery point objective describes the maximum acceptable data loss measured in time; recovery time objective describes the acceptable restoration duration. For example, a fictional workspace might target fifteen minutes of data loss and four hours to restore service. These are objectives to validate, not outcomes guaranteed by a backup schedule.

## Capture and retention

Combine periodic full snapshots with transaction-log or incremental capture when the storage engine supports point-in-time recovery. Ensure object versions and database records can be restored to a mutually consistent point, or document reconciliation steps for mismatches. Encrypt backup data, restrict access separately from production credentials, and retain an isolated copy protected from routine deletion.

```yaml
illustrative_policy:
  full_snapshot: daily
  log_capture: continuous
  daily_retention_days: 30
  restore_test: monthly
```

This policy is an example, not executable configuration. Retention must reflect legal requirements, deletion obligations, storage costs, and the time needed to notice corruption. Deleting a production record does not necessarily remove every backup copy immediately; document the applicable retention and access controls.

## Restore procedure

Restore into an isolated environment first. Select a recovery point, provision compatible software and keys, restore the database and attachments, then verify checksums and application invariants. Rebuild derived indexes from authoritative records or restore a matching index snapshot. Keep outbound notifications and scheduled jobs disabled until operators deliberately enable them, preventing restored data from triggering duplicate side effects.

Measure elapsed time from incident declaration to a usable application, not merely the snapshot download. Test a representative sample of private and public documents, permissions, and recent revisions. Record missing dependencies and update the runbook after each exercise.

## Failure scenarios

Monitor backup completion, log-capture gaps, age of the newest usable recovery point, and restore-test results. A successful upload is not proof that data can be decrypted or restored. Exercise accidental deletion, corrupted data, compromised credentials, and loss of a region. If a backup is suspected of containing malicious changes, preserve evidence and choose a recovery point before the compromise where possible.