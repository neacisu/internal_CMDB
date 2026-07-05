"""Tests for auth.spiffe — SPIFFE JWT-SVID validation stub."""

from __future__ import annotations

import pytest

from internalcmdb.auth.spiffe import SpiffeJwtValidator, SpiffeValidationError


def test_parse_spiffe_id_valid() -> None:
    parsed = SpiffeJwtValidator.parse_spiffe_id(
        "spiffe://internalcmdb.local/collector/hz-223"
    )
    assert parsed == ("internalcmdb.local", "collector", "hz-223")


def test_parse_spiffe_id_invalid() -> None:
    assert SpiffeJwtValidator.parse_spiffe_id("not-a-spiffe-id") is None


@pytest.mark.asyncio
async def test_validate_stub_without_jwks() -> None:
    validator = SpiffeJwtValidator(trust_domain="internalcmdb.local")
    claims = await validator.validate(
        "spiffe://internalcmdb.local/collector/hz-223"
    )
    assert claims.subject.endswith("hz-223")
    assert "internalcmdb-api" in claims.audience


@pytest.mark.asyncio
async def test_validate_empty_token_raises() -> None:
    validator = SpiffeJwtValidator()
    with pytest.raises(SpiffeValidationError):
        await validator.validate("")
