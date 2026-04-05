"""Tests for api.middleware.rbac."""
from __future__ import annotations
import base64
import json
from unittest.mock import patch
import pytest
from fastapi import HTTPException, Request


def _make_request(headers=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


def _make_jwt_token(claims):
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def test_extract_roles_zitadel_dict():
    from internalcmdb.api.middleware.rbac import _extract_roles
    claims = {"urn:zitadel:iam:org:project:roles": {"admin": {}, "viewer": {}}}
    roles = _extract_roles(claims)
    assert "admin" in roles and "viewer" in roles


def test_extract_roles_list_claim():
    from internalcmdb.api.middleware.rbac import _extract_roles
    claims = {"urn:zitadel:iam:org:project:roles": ["Admin", "hitl_reviewer"]}
    roles = _extract_roles(claims)
    assert "admin" in roles and "hitl_reviewer" in roles


def test_extract_roles_realm_access():
    from internalcmdb.api.middleware.rbac import _extract_roles
    claims = {"realm_access": {"roles": ["operator", "admin"]}}
    roles = _extract_roles(claims)
    assert "operator" in roles and "admin" in roles


def test_extract_roles_groups():
    from internalcmdb.api.middleware.rbac import _extract_roles
    claims = {"groups": ["/admins", "/users"]}
    roles = _extract_roles(claims)
    assert "/admins" in roles


def test_extract_roles_empty():
    from internalcmdb.api.middleware.rbac import _extract_roles
    assert _extract_roles({}) == set()


def test_decode_jwt_claims_valid_token():
    from internalcmdb.api.middleware.rbac import _decode_jwt_claims
    claims = {"sub": "user-123", "email": "test@example.com"}
    token = _make_jwt_token(claims)
    decoded = _decode_jwt_claims(token)
    assert decoded.get("sub") == "user-123"


def test_decode_jwt_claims_invalid_token():
    from internalcmdb.api.middleware.rbac import _decode_jwt_claims
    assert _decode_jwt_claims("not.a.jwt") == {}


def test_decode_jwt_claims_malformed():
    from internalcmdb.api.middleware.rbac import _decode_jwt_claims
    assert _decode_jwt_claims("onlyonepart") == {}


def test_get_bearer_token_present():
    from internalcmdb.api.middleware.rbac import _get_bearer_token
    req = _make_request({"authorization": "Bearer my-token"})
    assert _get_bearer_token(req) == "my-token"


def test_get_bearer_token_absent():
    from internalcmdb.api.middleware.rbac import _get_bearer_token
    assert _get_bearer_token(_make_request()) is None


def test_get_bearer_token_non_bearer():
    from internalcmdb.api.middleware.rbac import _get_bearer_token
    assert _get_bearer_token(_make_request({"authorization": "Basic dXNlcjpwYXNz"})) is None


def test_require_role_dev_mode_passes():
    import internalcmdb.api.middleware.rbac as rbac_module
    with patch.object(rbac_module, "_DEV_MODE", True):
        from internalcmdb.api.middleware.rbac import require_role
        dep = require_role("admin")
        dep(request=_make_request(), token=None)


def test_require_role_no_token_raises_401():
    import internalcmdb.api.middleware.rbac as rbac_module
    with patch.object(rbac_module, "_DEV_MODE", False):
        from internalcmdb.api.middleware.rbac import require_role
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(request=_make_request(), token=None)
        assert exc.value.status_code == 401


def test_require_role_invalid_token_raises_401():
    import internalcmdb.api.middleware.rbac as rbac_module
    with patch.object(rbac_module, "_DEV_MODE", False):
        from internalcmdb.api.middleware.rbac import require_role
        dep = require_role("admin")
        with pytest.raises(HTTPException) as exc:
            dep(request=_make_request(), token="not.a.jwt")
        assert exc.value.status_code == 401


def test_require_role_wrong_role_raises_403():
    import internalcmdb.api.middleware.rbac as rbac_module
    with patch.object(rbac_module, "_DEV_MODE", False):
        from internalcmdb.api.middleware.rbac import require_role
        dep = require_role("admin")
        claims = {"sub": "u1", "urn:zitadel:iam:org:project:roles": {"viewer": {}}}
        with pytest.raises(HTTPException) as exc:
            dep(request=_make_request(), token=_make_jwt_token(claims))
        assert exc.value.status_code == 403


def test_require_role_correct_role_passes():
    import internalcmdb.api.middleware.rbac as rbac_module
    with patch.object(rbac_module, "_DEV_MODE", False):
        from internalcmdb.api.middleware.rbac import require_role
        dep = require_role("admin")
        req = _make_request()
        claims = {"sub": "u1", "urn:zitadel:iam:org:project:roles": {"admin": {}}}
        dep(request=req, token=_make_jwt_token(claims))
        assert req.state.rbac_sub == "u1"
        assert "admin" in req.state.rbac_roles


def test_fetch_jwks_sync_returns_cached():
    import internalcmdb.api.middleware.rbac as rbac_module
    rbac_module._jwks_cache = {"keys": [{"kid": "test-key"}]}
    rbac_module._jwks_fetched_at = float("inf")
    result = rbac_module._fetch_jwks_sync()
    assert result == {"keys": [{"kid": "test-key"}]}
    rbac_module._jwks_cache = {}
    rbac_module._jwks_fetched_at = 0


def test_fetch_jwks_sync_network_error():
    import internalcmdb.api.middleware.rbac as rbac_module
    rbac_module._jwks_cache = {}
    rbac_module._jwks_fetched_at = 0
    with patch("internalcmdb.api.middleware.rbac._ZITADEL_ISSUER", "https://issuer.example.com"):
        with patch("httpx.get", side_effect=ConnectionError("unreachable")):
            result = rbac_module._fetch_jwks_sync()
    assert result == {}
