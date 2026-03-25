"""Collector: certificate_state — TLS cert subject, expiry, issuer, chain depth. Tier: 1h.

Connections use the platform trust store, TLS 1.2+ (client min), full certificate
validation and hostname checks (RFC 6125). For hosts signed by a private CA, install
that CA in the system bundle or point the agent at ``SSL_CERT_FILE`` / ``SSL_CERT_DIR``
before starting the collector process.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any

DEFAULT_ENDPOINTS: list[dict[str, Any]] = [
    {"host": "127.0.0.1", "port": 443},
]


def _rdn_tuple_to_dict(rdn_sequence: tuple[Any, ...]) -> dict[str, str]:
    """Flatten OpenSSL-style subject/issuer tuples into a single attribute map."""
    if not rdn_sequence:
        return {}
    return {k: v for group in rdn_sequence for k, v in group}


def _verified_chain_depth(ssock: ssl.SSLSocket, has_der: bool) -> int:
    """Number of certificates in the verified chain (leaf → roots), if exposed by ssl."""
    if not has_der:
        return 0
    try:
        verified = ssock.get_verified_chain()
    except (AttributeError, ValueError, ssl.SSLError):
        return 1
    return len(verified) if verified else 1


def _check_cert(host: str, port: int = 443, timeout: float = 5.0) -> dict[str, Any]:
    """Connect via TLS and extract certificate details."""
    ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    # Hostname verification and CERT_REQUIRED are defaults on create_default_context;
    # keep them explicit for security review / static analysis alignment.
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock, \
             ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert(binary_form=False)
            der = ssock.getpeercert(binary_form=True)
            chain_depth = _verified_chain_depth(ssock, bool(der))

            if not cert:
                return {
                    "host": host,
                    "port": port,
                    "error": "no certificate returned",
                }

            not_after_str = cert.get("notAfter", "")
            subject_parts = cert.get("subject", ())
            issuer_parts = cert.get("issuer", ())

            subject = _rdn_tuple_to_dict(subject_parts)
            issuer = _rdn_tuple_to_dict(issuer_parts)

            expiry_dt = None
            days_until_expiry = None
            if not_after_str:
                try:
                    expiry_dt = datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z").replace(
                        tzinfo=timezone.utc
                    )
                    days_until_expiry = (expiry_dt - datetime.now(timezone.utc)).days
                except ValueError:
                    pass

            return {
                "host": host,
                "port": port,
                "subject": subject.get("commonName", str(subject)),
                "issuer": issuer.get("organizationName", str(issuer)),
                "not_after": not_after_str,
                "days_until_expiry": days_until_expiry,
                "chain_depth": chain_depth,
                "serial_number": cert.get("serialNumber"),
            }
    except ConnectionRefusedError:
        return {"host": host, "port": port, "error": "connection_refused"}
    except TimeoutError:
        return {"host": host, "port": port, "error": "timeout"}
    except ssl.SSLError as exc:
        return {"host": host, "port": port, "error": f"ssl_error: {exc}"}
    except OSError as exc:
        return {"host": host, "port": port, "error": str(exc)}


def collect(endpoints: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Check TLS certificates on configured endpoints."""
    targets = endpoints or DEFAULT_ENDPOINTS
    results = [_check_cert(ep["host"], ep.get("port", 443)) for ep in targets]
    expiring_soon = sum(
        1
        for r in results
        if r.get("days_until_expiry") is not None and r["days_until_expiry"] < 30  # noqa: PLR2004
    )
    return {
        "certificates": results,
        "total": len(results),
        "expiring_soon_30d": expiring_soon,
    }
