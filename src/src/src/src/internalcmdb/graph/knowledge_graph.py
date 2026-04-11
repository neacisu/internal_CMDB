"""Infrastructure Knowledge Graph — topology, impact analysis, dependency detection.

Builds a directed graph from the registry (hosts, services, dependencies, ci_relationship)
and provides queries for blast radius, circular dependency detection, and topology diffing.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _service_dependency_target_id(row: Any) -> str | None:
    """Resolve dependency target: instance id preferred, else shared_service id."""
    if row.target_service_instance_id:
        return str(row.target_service_instance_id)
    if row.target_shared_service_id:
        return str(row.target_shared_service_id)
    return None


def _ci_confidence(row: Any) -> float:
    """Normalise optional confidence from ci_relationship row."""
    if row.confidence is not None:
        return float(row.confidence)
    return 1.0


class InfrastructureKnowledgeGraph:
    """Builds and queries an infrastructure dependency graph from the CMDB registry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._graph: nx.DiGraph = nx.DiGraph()

    async def _ingest_hosts(self, g: nx.DiGraph) -> None:
        result = await self._session.execute(
            text("SELECT host_id, hostname, host_code FROM registry.host")
        )
        for row in result.fetchall():
            g.add_node(
                str(row.host_id),
                kind="host",
                label=row.hostname,
                code=row.host_code,
            )

    async def _ingest_shared_services(self, g: nx.DiGraph) -> None:
        result = await self._session.execute(
            text(
                "SELECT shared_service_id, name, service_code "
                "FROM registry.shared_service WHERE is_active = true"
            )
        )
        for row in result.fetchall():
            g.add_node(
                str(row.shared_service_id),
                kind="shared_service",
                label=row.name,
                code=row.service_code,
            )

    async def _ingest_service_instances(self, g: nx.DiGraph) -> None:
        result = await self._session.execute(
            text(
                "SELECT service_instance_id, shared_service_id, host_id, instance_name "
                "FROM registry.service_instance"
            )
        )
        for row in result.fetchall():
            node_id = str(row.service_instance_id)
            g.add_node(node_id, kind="service_instance", label=row.instance_name)
            if row.shared_service_id:
                g.add_edge(
                    str(row.shared_service_id),
                    node_id,
                    relation="has_instance",
                )
            if row.host_id:
                g.add_edge(node_id, str(row.host_id), relation="runs_on")

    async def _ingest_service_dependencies(self, g: nx.DiGraph) -> None:
        result = await self._session.execute(
            text(
                "SELECT source_service_instance_id, target_service_instance_id, "
                "target_shared_service_id, is_hard_dependency "
                "FROM registry.service_dependency"
            )
        )
        for row in result.fetchall():
            src = str(row.source_service_instance_id)
            tgt = _service_dependency_target_id(row)
            if tgt:
                g.add_edge(
                    src,
                    tgt,
                    relation="depends_on",
                    hard=bool(row.is_hard_dependency),
                )

    async def _ingest_ci_relationships(self, g: nx.DiGraph) -> None:
        ci_exists = await self._session.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_schema = 'registry' AND table_name = 'ci_relationship'"
                ")"
            )
        )
        if not ci_exists.scalar():
            return

        ci_rels = await self._session.execute(
            text(
                "SELECT source_entity_id, target_entity_id, relationship_type, confidence "
                "FROM registry.ci_relationship WHERE is_active = true"
            )
        )
        for row in ci_rels.fetchall():
            g.add_edge(
                str(row.source_entity_id),
                str(row.target_entity_id),
                relation=row.relationship_type,
                confidence=_ci_confidence(row),
            )

    async def build_graph(self) -> nx.DiGraph:
        """Build a directed graph from hosts, services, dependencies, and ci_relationships."""
        g = nx.DiGraph()
        await self._ingest_hosts(g)
        await self._ingest_shared_services(g)
        await self._ingest_service_instances(g)
        await self._ingest_service_dependencies(g)
        await self._ingest_ci_relationships(g)
        self._graph = g
        return g

    async def impact_analysis(
        self, entity_id: str, action_type: str = "shutdown"
    ) -> dict[str, Any]:
        """Find all downstream entities affected if *entity_id* is acted upon."""
        if not self._graph.number_of_nodes():
            await self.build_graph()

        if entity_id not in self._graph:
            return {"entity_id": entity_id, "action": action_type, "affected": [], "count": 0}

        downstream = nx.descendants(self._graph, entity_id)
        affected: list[dict[str, Any]] = []
        for nid in downstream:
            data = self._graph.nodes[nid]
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
        }

    async def blast_radius(self, entity_id: str, depth: int = 3) -> set[str]:
        """Return entity IDs within *depth* hops (both directions) of *entity_id*."""
        if not self._graph.number_of_nodes():
            await self.build_graph()

        if entity_id not in self._graph:
            return set()

        undirected = self._graph.to_undirected()
        reachable: set[str] = set()
        for node, d in nx.single_source_shortest_path_length(
            undirected, entity_id, cutoff=depth
        ).items():
            if d > 0:
                reachable.add(node)

        return reachable

    async def detect_circular_dependencies(self, limit: int = 100) -> list[list[str]]:
        """Find simple cycles in the dependency graph (capped at *limit*)."""
        if not self._graph.number_of_nodes():
            await self.build_graph()

        try:
            cycles: list[list[str]] = []
            for cycle in nx.simple_cycles(self._graph):
                cycles.append(cycle)
                if len(cycles) >= limit:
                    break
        except nx.NetworkXError:
            cycles = []

        return cycles

    def topology_diff(
        self, snapshot_a: dict[str, Any], snapshot_b: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare two topology snapshots (JSON with 'nodes' and 'edges' keys).

        Returns added/removed nodes and edges. Synchronous — pure in-memory set
        operations; use from async endpoints without ``await`` (or wrap in
        :func:`asyncio.to_thread` only if snapshots are huge).
        """
        nodes_a = {n["id"] for n in snapshot_a.get("nodes", [])}
        nodes_b = {n["id"] for n in snapshot_b.get("nodes", [])}

        def _edge_key(e: dict[str, Any]) -> tuple[str, str]:
            return (e["source"], e["target"])

        edges_a = {_edge_key(e) for e in snapshot_a.get("edges", [])}
        edges_b = {_edge_key(e) for e in snapshot_b.get("edges", [])}

        return {
            "nodes_added": list(nodes_b - nodes_a),
            "nodes_removed": list(nodes_a - nodes_b),
            "edges_added": [{"source": s, "target": t} for s, t in edges_b - edges_a],
            "edges_removed": [{"source": s, "target": t} for s, t in edges_a - edges_b],
        }

    def to_json(self) -> dict[str, Any]:
        """Serialize the current graph as JSON-compatible dict."""
        nodes = []
        for nid, data in self._graph.nodes(data=True):
            nodes.append({"id": nid, **data})

        edges = []
        for src, tgt, data in self._graph.edges(data=True):
            edges.append({"source": src, "target": tgt, **data})

        return {"nodes": nodes, "edges": edges}
