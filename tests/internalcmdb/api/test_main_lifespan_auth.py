"""Tests for AUTH_DEV_MODE startup guard in api.main lifespan."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_lifespan_rejects_auth_dev_mode_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_DEV_MODE", "true")
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "p" * 32)
    monkeypatch.setenv("SECRET_KEY", "s" * 32)

    from internalcmdb.api.main import lifespan  # noqa: PLC0415

    app = MagicMock()
    provider = AsyncMock()
    provider.__aenter__ = AsyncMock(return_value=provider)
    provider.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("internalcmdb.api.main.get_settings") as settings_mock,
        patch("internalcmdb.config.secrets.SecretProvider", return_value=provider),
        patch("internalcmdb.config.secrets.is_placeholder_secret", return_value=False),
        patch("internalcmdb.auth.security.set_jwt_secret_ring"),
        patch("internalcmdb.observability.logging.setup_logging"),
        patch("internalcmdb.observability.tracing.setup_tracing", return_value=None),
    ):
        settings = MagicMock()
        settings.embedding_vector_dim = 4096
        settings.log_format = "json"
        settings.log_level = "INFO"
        settings.otlp_endpoint = "http://localhost:4317"
        settings.otlp_protocol = "grpc"
        settings.otlp_insecure = True
        settings.otel_sample_rate = 1.0
        settings_mock.return_value = settings
        provider.get = AsyncMock(side_effect=["secret-key-value", None])
        provider.get_jwt_secret_ring = AsyncMock(return_value=["j" * 32])

        with pytest.raises(RuntimeError, match="AUTH_DEV_MODE"):
            async with lifespan(app):
                pass
