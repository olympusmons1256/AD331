# DNS for Documentation Services

This page describes a fictional platform named Meridian. Hostnames, addresses, and durations are illustrative examples, not records for a real deployment.

## Names and resolution paths

Meridian uses a public hostname for the documentation gateway and internal names for private service endpoints. A client normally asks a recursive resolver, which may answer from cache or follow the authoritative delegation chain. A successful lookup identifies an address, not the identity of the process listening there; TLS validation remains necessary after resolution.

Keep public and private namespaces intentionally separated. If the same name resolves differently inside and outside the network, document which resolver each workload uses and test both views. Unplanned split-horizon behavior can make a service reachable from a laptop but unreachable from a container, or cause internal traffic to hairpin through a public gateway.

## Time to live and changes

The time to live describes how long a resolver may cache an answer. It is not a guaranteed global cutover timer: clients, intermediate caches, and existing connections may retain old destinations longer. Before a planned migration, lower the TTL sufficiently early for the previous value to expire, then verify observed resolver behavior. Keep the old endpoint healthy during the overlap whenever possible.

```text
docs.example.invalid.  60  IN  A     192.0.2.10
docs.example.invalid.  60  IN  AAAA  2001:db8::10
```

These reserved example addresses are placeholders. Dual-stack publication requires working IPv4 and IPv6 paths, matching firewall policy, and valid certificates on both destinations. A broken IPv6 path can create intermittent delays even when IPv4 works.

## Negative answers and failure modes

Resolvers can cache nonexistence or other negative responses according to authoritative zone settings. Creating a missing record therefore may not immediately repair clients that recently received a negative answer. Distinguish an authoritative nonexistent-name response from a timeout, temporary server failure, and an empty answer for a particular record type; each suggests a different investigation.

Search domains can also transform a short service name into unexpected queries. Prefer fully qualified names in critical configuration and avoid relying on environment-specific suffix ordering. Limit resolver retries and include DNS time in the request's overall deadline.

## Operational checks

Monitor authoritative response health, delegation consistency, lookup latency, and the difference between expected and observed records from several networks. During a change, record the old and new addresses, TTL, and rollback plan. Avoid placing sensitive topology in publicly accessible records. When troubleshooting, inspect both the resolver's cached answer and the authoritative answer before assuming that every client sees the same state.