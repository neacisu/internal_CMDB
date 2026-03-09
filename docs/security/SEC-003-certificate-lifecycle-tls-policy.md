---
id: SEC-003
title: internalCMDB — Certificate Lifecycle and TLS Policy (Wave-1)
doc_class: policy_pack
domain: security
version: "1.0"
status: approved
created: 2026-03-08
updated: 2026-03-08
owner: security_and_policy_owner
tags: [tls, certificates, lifecycle, wave-1, m9-3]
depends_on: [SEC-001, SEC-002]
---

# internalCMDB — Certificate Lifecycle and TLS Policy

## 1. Purpose

TLS lifecycle policy with issuance, renewal, expiry, and failure handling procedures.
Satisfies pt-030 [m9-3].

---

## 2. Wave-1 TLS Scope

In Wave-1 (single-node, internal-only deployment), internalCMDB services are exposed only on the Hetzner vSwitch private subnet. TLS scope is:

| Surface | TLS Required | Justification |
| --- | --- | --- |
| PostgreSQL (internal Docker network) | NO (Wave-1) | Container-to-container on internal Docker bridge; no external exposure |
| Application API (vSwitch) | OPTIONAL (Wave-1) | Internal cluster traffic; TLS expected for Wave-2 |
| Open WebUI (vSwitch port 3000) | NO (Wave-1) | Internal access only |
| SSH access (host) | YES (always) | Not TLS but key-based SSH — covered by SEC-002 |

**Wave-2 requirement**: All vSwitch-facing API endpoints must be TLS-terminated before promotion to wave-2.

---

## 3. Certificate Issuance Policy

When TLS is activated (Wave-2 readiness):

| Property | Policy |
| --- | --- |
| Certificate Authority | Let's Encrypt (public) or internal CA (private subnet) |
| Minimum key length | RSA 2048 or Ed25519 |
| TLS version | TLS 1.2 minimum; TLS 1.3 preferred |
| Cipher suites | ECDHE-RSA/ECDSA + AES-GCM; no RC4, no DES, no 3DES |
| Certificate validity | Max 90 days (Let's Encrypt standard) |
| SANs required | Must match all service endpoints; no wildcard for production |

---

## 4. Renewal Procedures

### 4.1 Let's Encrypt Auto-Renewal (Certbot)

```bash
# Install certbot
apt install -y certbot

# Standalone renewal (stop service temporarily)
certbot certonly --standalone -d <hostname>

# Verify renewal configuration
certbot renew --dry-run

# Auto-renewal cron (runs twice daily)
# /etc/cron.d/certbot already installed by package
```

### 4.2 Internal CA Certificate (if used)

```bash
# Generate new certificate from internal CA
openssl req -newkey rsa:2048 -nodes -keyout service.key \
  -out service.csr -subj "/CN=internalcmdb-api"

# Sign with internal CA
openssl x509 -req -in service.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out service.crt -days 90

# Deploy: copy to /etc/ssl/internalcmdb/ with mode 600 for .key
# Reload service
docker compose up -d --force-recreate
```

---

## 5. Expiry Monitoring

| Check | Method | Frequency |
| --- | --- | --- |
| Certificate expiry alert | `openssl x509 -noout -dates -in cert.pem` or Prometheus `ssl_expiry_gauge` | Weekly |
| Alert threshold | 30 days before expiry → WARNING; 7 days → CRITICAL | Continuous |
| Responsible action | platform_architecture_lead initiates renewal; security_and_policy_owner confirms |  |

---

## 6. TLS Failure Handling

| Failure Scenario | Response Procedure |
| --- | --- |
| Certificate expired | Immediate renewal via §4; service restart; post-incident entry in change_log |
| Private key compromise suspected | Revoke immediately; reissue; rotate all service tokens that used that key |
| CA root compromise | Escalate to security_and_policy_owner; reissue from new CA; notify all dependent services |
| TLS handshake failures detected | Check cipher/version compatibility; review server TLS config; escalate if unexplained |
| Certbot renewal failure | Check port 80 availability; verify DNS; manual renewal fallback via §4.2 |

---

## 7. Verification

- [x] Wave-1 TLS scope explicitly defined (no unexplained gaps).
- [x] Issuance policy covers minimum key length, TLS version, and cipher suites.
- [x] Renewal procedure executable without ad-hoc invention.
- [x] Expiry monitoring frequency and thresholds defined.
- [x] Failure handling covers all critical certificate failure modes.
