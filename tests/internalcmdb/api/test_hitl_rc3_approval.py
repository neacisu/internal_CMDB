"""Tests for RC-3 platform_admin approval restriction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.hitl import router as hitl_router


async def _rc3_session():
    session = AsyncMock()
    risk_result = MagicMock()
    risk_result.fetchone.return_value = ("RC-3",)
    empty_result = MagicMock()
    empty_result.fetchone.return_value = None
    session.execute = AsyncMock(side_effect=[risk_result, empty_result])
    yield session


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def inject_role(request, call_next):
        request.state.rbac_role = "hitl_reviewer"
        return await call_next(request)

    app.dependency_overrides[get_async_session] = _rc3_session
    app.include_router(hitl_router, prefix="/api/v1")
    return app


def test_rc3_approve_rejects_non_platform_admin() -> None:
    with patch("internalcmdb.api.routers.hitl.AUTH_DEV_MODE", False):
        client = TestClient(_make_app())
        r = client.post(
            "/api/v1/hitl/queue/item-1/approve",
            json={"reason": "ok"},
        )
    assert r.status_code == 403
    assert "platform_admin" in r.json()["detail"]
