# Lantern storage, backups, and recovery

Lantern is the fictional Lattice Harbor inventory service. Its relational database holds tenant inventory and an append-only audit trail. The service uses a primary for writes and read replicas for selected reporting queries. Replicas may lag, so immediately reading a write from a replica is not guaranteed to return the latest value. Requests requiring read-after-write behavior are routed to the primary.

## Backup chain

The example recovery plan combines scheduled base snapshots with an archived transaction log. A base snapshot is useful only if the matching log segments are retained and can be replayed. Backups and encryption keys live in a separate administrative boundary from the primary database. The backup catalog records snapshot time, log coverage, checksum, and the key reference; it does not contain plaintext encryption keys.

## Restore drill

A restore starts in an isolated environment. Operators select a snapshot, verify the checksums, replay logs up to a chosen point, and compare the recovered schema and sample records against independent expectations. Only after the application passes checks should the restored database be considered for promotion. Recovery time includes provisioning, replay, validation, and traffic cutover, not just downloading a snapshot.

## Failure considerations

An automated backup success message is not proof of a usable restore. Missing logs, expired keys, incompatible application versions, and corrupted snapshots can all defeat recovery. Record the observed results of actual drills separately from target recovery objectives. No drill or performance measurement is asserted by this fictional page.