"""Staleness detector — background task that marks agents degraded/offline."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.collectors.schedule_tiers import TIERS
from internalcmdb.models.collectors import CollectorAgent

logger = logging.getLogger(__name__)

# Multipliers for staleness detection
DEGRADED_MULTIPLIER = 3
OFFLINE_MULTIPLIER = 10

# Use the shortest tier (heartbeat 5s) as the base interval
BASE_INTERVAL = TIERS["5s"].interval_seconds


def check_staleness(db: Session) -> dict[str, int]:
    """Check all active agents and update status based on heartbeat freshness.

    Returns a dict with counts: {degraded: N, offline: N, recovered: N}.
    """
    now = datetime.now(UTC)
    degraded_cutoff = now - timedelta(seconds=BASE_INTERVAL * DEGRADED_MULTIPLIER)
    offline_cutoff = now - timedelta(seconds=BASE_INTERVAL * OFFLINE_MULTIPLIER)

    agents = db.scalars(
        select(CollectorAgent).where(
            CollectorAgent.is_active.is_(True),
            CollectorAgent.status != "retired",
        )
    ).all()

    counts = {"degraded": 0, "offline": 0, "recovered": 0}

    for agent in agents:
        if agent.last_heartbeat_at is None:
            continue

        # Parse the heartbeat timestamp
        try:
            last_hb = datetime.fromisoformat(str(agent.last_heartbeat_at))
            if last_hb.tzinfo is None:
                last_hb = last_hb.replace(tzinfo=UTC)
        except ValueError, TypeError:
            continue

        old_status = agent.status

        if last_hb < offline_cutoff:
            agent.status = "offline"
        elif last_hb < degraded_cutoff:
            agent.status = "degraded"
        else:
            agent.status = "online"

        if old_status != agent.status:
            if agent.status == "degraded":
                counts["degraded"] += 1
            elif agent.status == "offline":
                counts["offline"] += 1
            elif agent.status == "online" and old_status in ("degraded", "offline"):
                counts["recovered"] += 1

            logger.info(
                "Agent %s (%s): %s → %s",
                agent.agent_id,
                agent.host_code,
                old_status,
                agent.status,
            )

    db.commit()
    return counts


def run_staleness_check() -> None:
    """Standalone entry point for the staleness detector."""
    from sqlalchemy import create_engine  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = factory()
    try:
        counts = check_staleness(db)
        logger.info("Staleness check: %s", counts)
    finally:
        db.close()
        engine.dispose()
