# TLS and Internal Transport Identity

Meridian is a fictional documentation platform. The certificate names, durations, and settings here are illustrative and do not describe an actual vendor interface.

## Establishing trust

TLS protects bytes in transit and allows a client to verify the server it intended to reach. Meridian terminates public TLS at its edge and uses authenticated TLS for internal service calls. Where mutual TLS is enabled, both sides present credentials; the server must still authorize the client's service identity for the requested operation. Encryption alone does not grant permission to read a document.

Clients verify the certificate chain, validity interval, and expected service name. They must not disable verification to work around an expired certificate or hostname mismatch. The expected name comes from trusted configuration, not an arbitrary request header. Protect private keys with restricted filesystem permissions or a dedicated key-management system, and never include them in logs or support bundles.

## Certificate lifecycle

Issue certificates with a limited lifetime and renew them well before expiry. For illustration, a deployment could use a thirty-day certificate and begin renewal seven days before expiration. Actual values depend on the issuer's availability, automation reliability, and emergency recovery process. Alert on both failed renewal attempts and the remaining validity of certificates actually served by running processes.

During a certificate-authority transition, distribute the new trust anchor first, issue certificates from the new authority, and remove the old anchor only after all legitimate peers have migrated. Test both directions of mutual authentication. A trust bundle that contains the new authority does not guarantee that the server has reloaded its new certificate.

## Configuration and protocol constraints

```yaml
illustrative_transport:
  minimum_tls_version: "1.2"
  expected_peer: document-service.internal
  client_certificate_required: true
```

The example is intentionally generic. Use the strongest protocol versions supported by all intended peers and maintain a documented compatibility exception process. Cipher policy, hostname validation, and certificate reload behavior depend on the actual runtime; verify them through integration tests rather than assuming this sample configures a particular library.

## Diagnosing failures

Differentiate connection refusal, handshake failure, untrusted issuer, expired certificate, and authorization rejection in internal telemetry. Keep user-facing responses generic enough to avoid exposing private topology. Check system clock synchronization before replacing apparently invalid certificates. If a key is compromised, remove trust or revoke the credential according to the platform's enforcement capabilities, rotate affected keys, and investigate connections made during the exposure window.