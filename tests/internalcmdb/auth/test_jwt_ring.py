"""Tests for JWT key-ring behaviour in internalcmdb.auth.security."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException

from internalcmdb.auth.security import (
    TokenClaims,
    create_access_token,
    decode_access_token,
    invalidate_jwt_secret_cache,
    set_jwt_secret_ring,
)

_CURRENT = "a" * 32
_PREVIOUS = "b" * 32


@pytest.fixture(autouse=True)
def _reset_ring() -> Iterator[None]:
    set_jwt_secret_ring([_CURRENT])
    yield
    invalidate_jwt_secret_cache()


def test_decode_accepts_previous_key_in_ring() -> None:
    token, _, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "admin"))
    set_jwt_secret_ring([_PREVIOUS, _CURRENT])
    payload = decode_access_token(token)
    assert payload.sub == "u"


def test_create_always_uses_current_key() -> None:
    set_jwt_secret_ring([_PREVIOUS, _CURRENT])
    token, _, _ = create_access_token(TokenClaims("u", "u@e.com", "u", "admin"))
    set_jwt_secret_ring([_CURRENT])
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401


def test_set_jwt_secret_ring_rejects_short_keys() -> None:
    with pytest.raises(RuntimeError, match="32"):
        set_jwt_secret_ring(["short"])
