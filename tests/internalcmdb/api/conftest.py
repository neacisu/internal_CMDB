"""pytest fixtures for internalcmdb API router tests.

Sets AUTH_DEV_MODE=True so all router tests bypass JWT auth.
This mirrors the dev-mode behaviour that was in place before the auth
module was written and keeps existing router tests green without requiring
them to provide valid JWT tokens.

Integration tests that need to verify auth enforcement explicitly should
``monkeypatch.setenv("AUTH_DEV_MODE", "false")`` to override this.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _auth_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Globally bypass JWT auth for all internalcmdb API unit tests."""
    monkeypatch.setattr(
        "internalcmdb.api.middleware.rbac.AUTH_DEV_MODE",
        True,
        raising=False,
    )
