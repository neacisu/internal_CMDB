"""Apache AGE graph backend with relational fallback (F5.2).

Provides a blast-radius query interface that prefers Apache AGE Cypher when
the extension is available, falling back to ``registry.graph_*`` tables or
the NetworkX-based :class:`~internalcmdb.graph.knowledge_graph.InfrastructureKnowledgeGraph`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_AGE_GRAPH_NAME = "internalcmdb_topology"


class AgeGraphBackend:
    """Blast-radius and impact queries via Apache AGE or relational fallback."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._age_available: bool | None = None

    async def is_age_available(self) -> bool:
        """Return True when the Apache AGE extension is installed."""
        if self._age_available is not None:
            return self._age_available
        result = await self._session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'age' LIMIT 1")
        )
        self._age_available = result.first() is not None
        return self._age_available

    async def blast_radius(
        self,
        entity_id: str,
        *,
        depth: int = 3,
        action_type: str = "shutdown",
    ) -> dict[str, Any]:
        """Return entities within *depth* hops of *entity_id*.

        Tries AGE Cypher first, then relational ``graph_*`` tables, then
        delegates to :class:`InfrastructureKnowledgeGraph`.
        """
        if await self.is_age_available():
            try:
                return await self._blast_radius_age(entity_id, depth=depth, action_type=action_type)
            except Exception:
                logger.warning(
                    "AGE blast_radius failed — falling back to relational", exc_info=True
                )

        relational = await self._blast_radius_relational(entity_id, depth=depth)
        if relational["count"] > 0:
            relational["action"] = action_type
            relational["backend"] = "relational"
            return relational

        from internalcmdb.graph.knowledge_graph import InfrastructureKnowledgeGraph  # noqa: PLC0415

        kg = InfrastructureKnowledgeGraph(self._session)
        reachable = await kg.blast_radius(entity_id, depth=depth)
        affected = []
        await kg.build_graph()
        for nid in reachable:
            data = kg._graph.nodes.get(nid, {})
            affected.append(
                {
                    "entity_id": nid,
                    "kind": data.get("kind", "unknown"),
                    "label": data.get("label", ""),
                }
            )
        return {
            "entity_id": entity_id,
            "action": action_type,
            "affected": affected,
            "count": len(affected),
            "backend": "networkx",
        }

    async def _blast_radius_age(
        self,
        entity_id: str,
        *,
        depth: int,
        action_type: str,
    ) -> dict[str, Any]:
        """Execute a bounded Cypher traversal via Apache AGE."""
        cypher = (
            f"MATCH (n {{entity_id: '{entity_id}'}})-[*1..{depth}]-(m) "
            "RETURN DISTINCT m.entity_id AS entity_id, m.entity_kind AS kind, m.label AS label"
        )
        sql = text(
            f"SELECT * FROM cypher('{_AGE_GRAPH_NAME}', $$ {cypher} $$) "
            "AS (entity_id agtype, kind agtype, label agtype)"
        )
        result = await self._session.execute(sql)
        affected: list[dict[str, Any]] = []
        for row in result.fetchall():
            affected.append(
                {
                    "entity_id": str(row.entity_id).strip('"'),
                    "kind": str(row.kind).strip('"') if row.kind else "unknown",
                    "label": str(row.label).strip('"') if row.label else "",
                }
            )
        return {
            "entity_id": entity_id,
            "action": action_type,
            "affected": affected,
            "count": len(affected),
            "backend": "age",
        }

    async def _blast_radius_relational(
        self,
        entity_id: str,
        *,
        depth: int,
    ) -> dict[str, Any]:
        """BFS over registry.graph_vertex / graph_edge fallback tables."""
        sql = text("""
            WITH RECURSIVE reach AS (
                SELECT v.vertex_id, v.entity_id::text AS entity_id,
                       v.entity_kind AS kind, v.label, 0 AS hop
                FROM registry.graph_vertex v
                WHERE v.entity_id::text = :entity_id AND v.is_active = true
                UNION
                SELECT v2.vertex_id, v2.entity_id::text, v2.entity_kind, v2.label, r.hop + 1
                FROM reach r
                JOIN registry.graph_edge e ON (
                    (e.source_vertex_id = r.vertex_id OR e.target_vertex_id = r.vertex_id)
                    AND e.is_active = true
                )
                JOIN registry.graph_vertex v2 ON (
                    v2.vertex_id = CASE
                        WHEN e.source_vertex_id = r.vertex_id THEN e.target_vertex_id
                        ELSE e.source_vertex_id
                    END
                    AND v2.is_active = true
                )
                WHERE r.hop < :depth
            )
            SELECT DISTINCT entity_id, kind, label FROM reach WHERE hop > 0
        """)
        result = await self._session.execute(sql, {"entity_id": entity_id, "depth": depth})
        affected = [
            {"entity_id": row.entity_id, "kind": row.kind, "label": row.label or ""}
            for row in result.fetchall()
        ]
        return {"entity_id": entity_id, "affected": affected, "count": len(affected)}


def get_graph_backend(session: AsyncSession) -> AgeGraphBackend:
    """Factory for the preferred graph query backend."""
    return AgeGraphBackend(session)
