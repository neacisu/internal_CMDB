"""Tests for internalcmdb.config.db_credentials."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from internalcmdb.api.config import Settings
from internalcmdb.config.db_credentials import (
    PostgresCredentialsProvider,
    build_database_url_sync,
    get_postgres_password_sync,
    invalidate_cache,
)
from internalcmdb.config.secrets import DatabaseStaticCreds, SecretProvider


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    invalidate_cache()
    yield
    invalidate_cache()


def test_get_password_sync_uses_static_creds() -> None:
    provider = PostgresCredentialsProvider()
    mock_sp = MagicMock()
    mock_sp.get_database_static_creds_sync.return_value = DatabaseStaticCreds(
        username="internalcmdb",
        password="rotated-pass",
    )
    provider._provider = mock_sp

    assert provider.get_password_sync() == "rotated-pass"
    assert provider.get_password_sync() == "rotated-pass"
    mock_sp.get_database_static_creds_sync.assert_called_once()


def test_build_database_url_includes_password() -> None:
    settings = Settings(
        postgres_host="db.local",
        postgres_port=5433,
        postgres_db="internalCMDB",
        postgres_user="internalcmdb",
        postgres_sslmode="require",
    )
    with patch(
        "internalcmdb.config.db_credentials.get_postgres_password_sync",
        return_value="s3cret",
    ):
        url = build_database_url_sync(settings)
    assert "internalcmdb:s3cret@db.local:5433/internalCMDB" in url
    assert "sslmode=require" in url


@pytest.mark.asyncio
async def test_invalidate_cache_forces_refetch() -> None:
    from internalcmdb.config import db_credentials  # noqa: PLC0415

    mock_sp = MagicMock()
    mock_sp.get_database_static_creds_sync.side_effect = [
        DatabaseStaticCreds(username="internalcmdb", password="first"),
        DatabaseStaticCreds(username="internalcmdb", password="second"),
    ]
    db_credentials._default_provider._provider = mock_sp

    assert get_postgres_password_sync() == "first"
    invalidate_cache()
    assert get_postgres_password_sync() == "second"
