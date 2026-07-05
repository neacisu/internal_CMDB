"""Tests for HITL decided_by sourced from authenticated user."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from internalcmdb.api.deps import get_async_session
from internalcmdb.api.routers.hitl import router as hitl_router


async def _session_factory():
    session = AsyncMock()
    risk_result = MagicMock()
    risk_result.fetchone.return_value = ("RC-1",)
    session.execute = AsyncMock(return_value=risk_result)
    wf_mock = MagicMock()
    wf_mock.approve = AsyncMock(return_value=True)
    yield session


def test_approve_uses_rbac_sub_not_body() -> None:
    app = FastAPI()

    @app.middleware("http")
    async def inject_sub(request, call_next):
        request.state.rbac_sub = "authenticated-user-id"
        request.state.rbac_role = "platform_admin"
        return await call_next(request)

    app.dependency_overrides[get_async_session] = _session_factory
    app.include_router(hitl_router, prefix="/api/v1")

    with patch("internalcmdb.api.routers.hitl.HITLWorkflow") as wf_cls:
        wf = MagicMock()
        wf.approve = AsyncMock(return_value=True)
        wf_cls.return_value = wf
        client = TestClient(app)
        resp = client.post(
            "/api/v1/hitl/queue/item-1/approve",
            json={"reason": "approved by test"},
        )

    assert resp.status_code == 200
    wf.approve.assert_awaited_once_with("item-1", "authenticated-user-id", "approved by test")
