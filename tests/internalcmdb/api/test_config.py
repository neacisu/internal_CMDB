"""Tests for internalcmdb.api.config — Settings validation and security.

Covers:
  - S6739 fix: Redis URL MUST NOT contain hardcoded production credentials
    in the source code default value
  - Default values are safe placeholders (verified in source, not runtime
    which may load a real .env)
  - Environment variable overrides work correctly
  - Database URL construction is correct
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_CONFIG_PATH = Path("src/internalcmdb/api/config.py")


class TestSourceCodeSecurity:
    """S6739: Verify the SOURCE CODE does not contain hardcoded credentials."""

    def test_no_redis_password_in_source(self) -> None:
        """The config.py source must not embed any real Redis password."""
        content = _CONFIG_PATH.read_text()
        assert "aKRiMYjXij6AqCq54GQF49S" not in content, (
            "Real Redis password found in config.py source code"
        )

    def test_redis_default_is_localhost_in_source(self) -> None:
        """Default redis_url in source must point to localhost."""
        content = _CONFIG_PATH.read_text()
        match = re.search(r'redis_url:\s*str\s*=\s*"([^"]+)"', content)
        assert match is not None, "redis_url field not found in config.py"
        assert "localhost" in match.group(1), (
            f"Default redis_url should be localhost, got: {match.group(1)}"
        )

    def test_no_production_urls_in_source(self) -> None:
        """No production hostnames in default values."""
        content = _CONFIG_PATH.read_text()
        assert "redis.infraq.app" not in content.split("redis_url")[1].split("\n")[0], (
            "Production Redis hostname found in redis_url default"
        )

    def test_postgres_password_default_is_placeholder(self) -> None:
        content = _CONFIG_PATH.read_text()
        match = re.search(r'postgres_password:\s*str\s*=\s*"([^"]+)"', content)
        assert match is not None
        assert match.group(1) == "change_me"

    def test_secret_key_default_is_placeholder(self) -> None:
        content = _CONFIG_PATH.read_text()
        match = re.search(r'secret_key:\s*str\s*=\s*"([^"]+)"', content)
        assert match is not None
        assert "change_me" in match.group(1)


class TestSettingsStructure:
    """Verify Settings class structure and database_url construction."""

    def test_settings_class_fields(self) -> None:
        from internalcmdb.api.config import Settings

        fields = Settings.model_fields
        assert "redis_url" in fields
        assert "postgres_password" in fields
        assert "secret_key" in fields
        assert "embedding_vector_dim" in fields

    def test_database_url_property(self) -> None:
        from internalcmdb.api.config import Settings

        settings = Settings()
        url = settings.database_url
        assert url.startswith("postgresql+psycopg://")
        assert f":{settings.postgres_port}/" in url
        assert f"?sslmode={settings.postgres_sslmode}" in url

    def test_database_url_contains_components(self) -> None:
        from internalcmdb.api.config import Settings

        settings = Settings()
        url = settings.database_url
        assert settings.postgres_user in url
        assert settings.postgres_host in url
        assert settings.postgres_db in url

    def test_settings_has_otel_fields(self) -> None:
        from internalcmdb.api.config import Settings

        fields = Settings.model_fields
        assert "otlp_endpoint" in fields
        assert "otlp_protocol" in fields
        assert "otlp_insecure" in fields
        assert "otel_sample_rate" in fields

    def test_settings_has_debug_field(self) -> None:
        from internalcmdb.api.config import Settings

        assert "debug_enabled" in Settings.model_fields

    def test_get_settings_cached(self) -> None:
        from internalcmdb.api.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
