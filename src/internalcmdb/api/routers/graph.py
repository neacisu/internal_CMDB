"""Router: graph — dependency graph topology and impact analysis."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.graph.knowledge_graph import InfrastructureKnowledgeGraph

from ..deps import get_async_session

router = APIRouter(prefix="/graph", tags=["graph"])


class ImpactRequest(BaseModel):
    entity_id: str
    action_type: str = Field(default="shutdown")


class TopologyDiffRequest(BaseModel):
    snapshot_a: dict[str, Any]
    snapshot_b: dict[str, Any]


_MAX_TOPOLOGY_NODES = 500


@router.get("/topology")
async def full_topology(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = Query(_MAX_TOPOLOGY_NODES, ge=1, le=5000),
) -> dict[str, Any]:
    """Infrastructure graph as JSON (nodes + edges), capped at *limit* nodes."""
    kg = InfrastructureKnowledgeGraph(session)
    await kg.build_graph()
    data = kg.to_json()
    if len(data["nodes"]) > limit:
        kept_ids = {n["id"] for n in data["nodes"][:limit]}
        data["nodes"] = data["nodes"][:limit]
        data["edges"] = [
            e for e in data["edges"] if e["source"] in kept_ids and e["target"] in kept_ids
        ]
        data["truncated"] = True
        data["total_nodes"] = kg._graph.number_of_nodes()
    return data


@router.get("/entity/{entity_id}/dependencies")
async def entity_dependencies(
    entity_id: str,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Upstream and downstream dependencies for a single entity."""
    kg = InfrastructureKnowledgeGraph(session)
    g = await kg.build_graph()

    upstream: list[dict[str, Any]] = []
    downstream: list[dict[str, Any]] = []

    if entity_id in g:
        for pred in g.predecessors(entity_id):
            data = g.nodes[pred]
            edge_data = g.edges[pred, entity_id]
            upstream.append({"entity_id": pred, **data, "relation": edge_data.get("relation")})

        for succ in g.successors(entity_id):
            data = g.nodes[succ]
            edge_data = g.edges[entity_id, succ]
            downstream.append({"entity_id": succ, **data, "relation": edge_data.get("relation")})

    return {
        "entity_id": entity_id,
        "upstream": upstream,
        "downstream": downstream,
    }


@router.post("/impact-analysis")
async def impact_analysis(
    body: ImpactRequest,
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Impact analysis for a proposed action on an entity."""
    kg = InfrastructureKnowledgeGraph(session)
    return await kg.impact_analysis(body.entity_id, body.action_type)


@router.get("/critical-paths")
async def critical_paths(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Find critical dependency paths (nodes with highest in-degree + out-degree)."""
    kg = InfrastructureKnowledgeGraph(session)
    g = await kg.build_graph()

    critical: list[dict[str, Any]] = []
    for nid, data in g.nodes(data=True):
        in_deg = g.in_degree(nid)
        out_deg = g.out_degree(nid)
        if in_deg + out_deg >= 2:  # noqa: PLR2004
            critical.append(
                {
                    "entity_id": nid,
                    "kind": data.get("kind", "unknown"),
                    "label": data.get("label", ""),
                    "in_degree": in_deg,
                    "out_degree": out_deg,
                    "total_connections": in_deg + out_deg,
                }
            )

    critical.sort(key=lambda x: x["total_connections"], reverse=True)
    return {"critical_nodes": critical[:50]}


@router.get("/circular-deps")
async def circular_dependencies(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict[str, Any]:
    """Detect circular dependencies in the infrastructure graph."""
    kg = InfrastructureKnowledgeGraph(session)
    cycles = await kg.detect_circular_dependencies()
    return {"cycles": cycles, "count": len(cycles)}
