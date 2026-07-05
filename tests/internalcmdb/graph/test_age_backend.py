"""Tests for graph.age_backend — blast-radius query interface."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from internalcmdb.graph.age_backend import AgeGraphBackend, get_graph_backend


@pytest.mark.asyncio
async def test_is_age_available_false() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = None
    session.execute = AsyncMock(return_value=result)

    backend = AgeGraphBackend(session)
    assert await backend.is_age_available() is False


@pytest.mark.asyncio
async def test_blast_radius_falls_back_to_networkx(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    age_result = MagicMock()
    age_result.first.return_value = None
    rel_result = MagicMock()
    rel_result.fetchall.return_value = []
    session.execute = AsyncMock(side_effect=[age_result, rel_result])

    class FakeKG:
        def __init__(self, _session: object) -> None:
            self._graph = MagicMock()
            self._graph.nodes = {"host-1": {"kind": "host", "label": "hz-223"}}

        async def blast_radius(self, entity_id: str, depth: int = 3) -> set[str]:
            return {"host-1"} if entity_id == "root" else set()

        async def build_graph(self) -> MagicMock:
            return self._graph

    monkeypatch.setattr(
        "internalcmdb.graph.knowledge_graph.InfrastructureKnowledgeGraph",
        FakeKG,
    )

    backend = AgeGraphBackend(session)
    result = await backend.blast_radius("root", depth=2)

    assert result["backend"] == "networkx"
    assert result["count"] == 1
    assert result["affected"][0]["entity_id"] == "host-1"


def test_get_graph_backend_is_sync() -> None:
    session = AsyncMock()
    backend = get_graph_backend(session)
    assert isinstance(backend, AgeGraphBackend)
    assert backend._session is session
