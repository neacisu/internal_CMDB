"""Fleet health helpers for mapping collector agents to known hosts."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.collectors.schedule_tiers import TIERS
from internalcmdb.models.collectors import CollectorAgent
from internalcmdb.models.registry import Host

DEGRADED_MULTIPLIER = 3
OFFLINE_MULTIPLIER = 10
BASE_INTERVAL = TIERS["5s"].interval_seconds


def _normalize_host_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _agent_sort_key(agent: CollectorAgent) -> tuple[datetime, datetime]:
    return (_parse_timestamp(agent.last_heartbeat_at), _parse_timestamp(agent.enrolled_at))


def _host_aliases(host: Host) -> set[str]:
    aliases = {
        _normalize_host_token(host.host_code),
        _normalize_host_token(host.hostname),
        _normalize_host_token(host.ssh_alias),
        _normalize_host_token(host.fqdn),
        _normalize_host_token(host.observed_hostname),
    }
    return {alias for alias in aliases if alias is not None}


def _parse_timestamp(raw: object) -> datetime:
    if raw is None:
        return datetime.min.replace(tzinfo=UTC)

    try:
        parsed = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=UTC)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def derive_agent_status(agent: CollectorAgent) -> str:
    if not agent.is_active:
        return "retired"
    if agent.status == "retired":
        return "retired"

    last_heartbeat = _parse_timestamp(agent.last_heartbeat_at)
    if last_heartbeat == datetime.min.replace(tzinfo=UTC):
        return "offline"

    now = datetime.now(UTC)
    degraded_cutoff = now - timedelta(seconds=BASE_INTERVAL * DEGRADED_MULTIPLIER)
    offline_cutoff = now - timedelta(seconds=BASE_INTERVAL * OFFLINE_MULTIPLIER)

    if last_heartbeat < offline_cutoff:
        return "offline"
    if last_heartbeat < degraded_cutoff:
        return "degraded"
    return "online"


def resolve_host(db: Session, host_code: str) -> Host | None:
    hosts = db.scalars(select(Host)).all()
    alias_index: dict[str, Host] = {}
    for host in hosts:
        for alias in _host_aliases(host):
            alias_index.setdefault(alias, host)
    return alias_index.get(_normalize_host_token(host_code) or "")


@dataclass(frozen=True)
class FleetState:
    hosts: Sequence[Host]
    agents_by_host_id: dict[uuid.UUID, CollectorAgent]
    unassigned_agents: list[CollectorAgent]


def build_fleet_state(db: Session) -> FleetState:
    hosts = db.scalars(select(Host).order_by(Host.host_code)).all()

    alias_to_host_id: dict[str, uuid.UUID] = {}
    host_ids: set[uuid.UUID] = set()
    for host in hosts:
        host_ids.add(host.host_id)
        for alias in _host_aliases(host):
            alias_to_host_id.setdefault(alias, host.host_id)

    agents = db.scalars(
        select(CollectorAgent).where(
            CollectorAgent.is_active.is_(True),
            CollectorAgent.status != "retired",
        )
    ).all()

    matched: dict[uuid.UUID, CollectorAgent] = {}
    unassigned: list[CollectorAgent] = []

    for agent in sorted(agents, key=_agent_sort_key, reverse=True):
        resolved_host_id = agent.host_id if agent.host_id in host_ids else None
        if resolved_host_id is None:
            resolved_host_id = alias_to_host_id.get(_normalize_host_token(agent.host_code) or "")

        if resolved_host_id is None:
            unassigned.append(agent)
            continue

        if resolved_host_id not in matched:
            matched[resolved_host_id] = agent
        else:
            unassigned.append(agent)

    return FleetState(hosts=hosts, agents_by_host_id=matched, unassigned_agents=unassigned)
