"""Tests for internalcmdb.api.middleware.rbac."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request as StarletteRequest

from internalcmdb.api.middleware import rbac as rbac_mod


def test_extract_roles_zitadel_dict() -> None:
    claims = {"urn:zitadel:iam:org:project:roles": {"Admin": {}, "Viewer": {}}}
    roles = rbac_mod._extract_roles(claims)
    assert "admin" in roles
    assert "viewer" in roles


def test_extract_roles_list_and_groups() -> None:
    claims = {
        "urn:zitadel:iam:org:project:roles": ["RoleA"],
        "realm_access": {"roles": ["offline_access"]},
        "groups": ["g1"],
    }
    roles = rbac_mod._extract_roles(claims)
    assert "rolea" in roles
    assert "offline_access" in roles
    assert "g1" in roles


def test_decode_jwt_claims_invalid_shape() -> None:
    assert rbac_mod._decode_jwt_claims("not-a-jwt") == {}


def test_decode_jwt_claims_valid_payload() -> None:
    payload = {"sub": "user-1", "email": "a@b.c"}
    b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    token = f"xx.{b64}.yy"
    out = rbac_mod._decode_jwt_claims(token)
    assert out.get("sub") == "user-1"


def test_get_bearer_token() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", b"Bearer tok123")],
    }
    req = StarletteRequest(scope)
    assert rbac_mod._get_bearer_token(req) == "tok123"


def test_require_role_missing_token_when_not_dev() -> None:
    dep = rbac_mod.require_role("admin")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [],
    }
    req = StarletteRequest(scope)
    if rbac_mod._DEV_MODE:
        dep(request=req, token=None)  # type: ignore[misc]
    else:
        with pytest.raises(HTTPException) as ei:
            dep(request=req, token=None)  # type: ignore[misc]
        assert ei.value.status_code == 401
