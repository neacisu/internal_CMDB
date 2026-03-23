"""Tests for model constant extraction — S1192 fixes.

Covers:
  - governance.py: _SERVER_NOW constant used instead of duplicate "now()" literals
  - retrieval.py: _SERVER_NOW constant used instead of duplicate "now()" literals
  - All server_default values reference the constant, not raw string literals
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


_GOVERNANCE_PATH = Path("src/internalcmdb/models/governance.py")
_RETRIEVAL_PATH = Path("src/internalcmdb/models/retrieval.py")


class TestGovernanceServerNow:
    """S1192: governance.py must use _SERVER_NOW constant."""

    def test_constant_defined(self) -> None:
        from internalcmdb.models.governance import _SERVER_NOW

        assert _SERVER_NOW == "now()"

    def test_no_raw_now_in_server_default(self) -> None:
        """No server_default='now()' raw literals should remain in governance.py."""
        content = _GOVERNANCE_PATH.read_text()
        matches = re.findall(r'server_default\s*=\s*"now\(\)"', content)
        assert len(matches) == 0, (
            f"Found {len(matches)} raw 'now()' literals in server_default — "
            "use _SERVER_NOW constant instead"
        )

    def test_server_default_uses_constant(self) -> None:
        """All server_default occurrences must reference _SERVER_NOW."""
        content = _GOVERNANCE_PATH.read_text()
        constant_uses = re.findall(r"server_default\s*=\s*_SERVER_NOW", content)
        assert len(constant_uses) >= 3, (
            f"Expected at least 3 uses of _SERVER_NOW in governance.py, "
            f"found {len(constant_uses)}"
        )


class TestRetrievalServerNow:
    """S1192: retrieval.py must use _SERVER_NOW constant."""

    def test_constant_defined(self) -> None:
        from internalcmdb.models.retrieval import _SERVER_NOW

        assert _SERVER_NOW == "now()"

    def test_no_raw_now_in_server_default(self) -> None:
        content = _RETRIEVAL_PATH.read_text()
        matches = re.findall(r'server_default\s*=\s*"now\(\)"', content)
        assert len(matches) == 0, (
            f"Found {len(matches)} raw 'now()' literals in server_default"
        )

    def test_server_default_uses_constant(self) -> None:
        content = _RETRIEVAL_PATH.read_text()
        constant_uses = re.findall(r"server_default\s*=\s*_SERVER_NOW", content)
        assert len(constant_uses) >= 4, (
            f"Expected at least 4 uses of _SERVER_NOW in retrieval.py, "
            f"found {len(constant_uses)}"
        )


class TestEmbeddingDim:
    """Embedding dimension must be configurable and have a valid default."""

    def test_embedding_dim_default(self) -> None:
        from internalcmdb.models.retrieval import _EMBEDDING_DIM

        assert _EMBEDDING_DIM == 4096

    def test_embedding_dim_is_int(self) -> None:
        from internalcmdb.models.retrieval import _EMBEDDING_DIM

        assert isinstance(_EMBEDDING_DIM, int)
