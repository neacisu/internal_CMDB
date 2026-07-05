"""SPIFFE JWT-SVID validation stub (F5.1).

Future integration point for zero-trust agent authentication.  Validates
JWT-SVIDs issued by SPIRE against the trust domain JWKS before mapping
SPIFFE IDs to collector agents.

Usage (planned)::

    validator = SpiffeJwtValidator(trust_domain="internalcmdb.local")
    claims = await validator.validate(token)
    spiffe_id = claims.subject  # spiffe://internalcmdb.local/collector/hz-223
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TRUST_DOMAIN = "internalcmdb.local"
_SPIFFE_PREFIX = "spiffe://"


@dataclass(frozen=True)
class SpiffeClaims:
    """Validated JWT-SVID claims."""

    subject: str
    audience: tuple[str, ...]
    expiry: int
    raw: dict[str, Any]


class SpiffeValidationError(Exception):
    """Raised when a JWT-SVID fails validation."""


class SpiffeJwtValidator:
    """Validate SPIFFE JWT-SVIDs against SPIRE JWKS (stub — not yet wired to middleware)."""

    def __init__(
        self,
        *,
        trust_domain: str | None = None,
        jwks_url: str | None = None,
        expected_audience: str = "internalcmdb-api",
    ) -> None:
        self.trust_domain = trust_domain or os.environ.get(
            "SPIFFE_TRUST_DOMAIN", _DEFAULT_TRUST_DOMAIN
        )
        self.jwks_url = jwks_url or os.environ.get("SPIFFE_JWKS_URL", "")
        self.expected_audience = expected_audience

    @staticmethod
    def is_enabled() -> bool:
        """Return True when SPIFFE auth is enabled via environment."""
        return os.environ.get("SPIFFE_AUTH_ENABLED", "false").lower() in ("1", "true", "yes")

    @staticmethod
    def parse_spiffe_id(subject: str) -> tuple[str, str, str] | None:
        """Parse ``spiffe://domain/component/id`` into (domain, component, id)."""
        if not subject.startswith(_SPIFFE_PREFIX):
            return None
        remainder = subject[len(_SPIFFE_PREFIX) :]
        parts = remainder.split("/", 2)
        if len(parts) < 3:
            return None
        return parts[0], parts[1], parts[2]

    async def validate(self, token: str) -> SpiffeClaims:
        """Validate a JWT-SVID and return parsed claims.

        Stub implementation: performs structural checks only.  Full JWKS
        signature verification will be added when SPIRE OIDC discovery is
        deployed.
        """
        if not token or not token.strip():
            raise SpiffeValidationError("empty token")

        if not self.jwks_url:
            logger.debug("SPIFFE JWKS URL not configured — returning stub claims for development")
            return await asyncio.to_thread(self._stub_claims, token)

        # Future: fetch JWKS, verify signature, check aud/exp/iss
        raise NotImplementedError(
            "JWT-SVID signature verification not yet implemented; "
            "set SPIFFE_JWKS_URL and deploy SPIRE OIDC discovery first"
        )

    def _stub_claims(self, token: str) -> SpiffeClaims:
        """Development-only stub when JWKS is unavailable."""
        # Accept bearer tokens shaped like spiffe://... for integration tests
        subject = token.removeprefix("Bearer ").strip()
        if not subject.startswith(_SPIFFE_PREFIX):
            subject = f"{_SPIFFE_PREFIX}{self.trust_domain}/collector/dev-stub"
        parsed = self.parse_spiffe_id(subject)
        if parsed is None or parsed[0] != self.trust_domain:
            raise SpiffeValidationError(f"invalid SPIFFE subject: {subject}")
        return SpiffeClaims(
            subject=subject,
            audience=(self.expected_audience,),
            expiry=0,
            raw={"sub": subject, "aud": self.expected_audience},
        )
