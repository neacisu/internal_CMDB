"""Staleness detector — background task that marks agents degraded/offline."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from internalcmdb.collectors.fleet_health import derive_agent_status
from internalcmdb.models.collectors import CollectorAgent

logger = logging.getLogger(__name__)


def _classify_status_change(old_status: str, new_status: str) -> str | None:
    """Return the counter key for a status transition, or None if uncounted.

    Returned values correspond to keys in the ``counts`` dict inside
    :func:`check_staleness`: ``"degraded"``, ``"offline"``, or ``"recovered"``.
    """
    if new_status == "degraded":
        return "degraded"
    if new_status == "offline":
        return "offline"
    if new_status == "online" and old_status in ("degraded", "offline"):
        return "recovered"
    return None


def check_staleness(db: Session) -> dict[str, int]:
    """Check all active agents and update status based on heartbeat freshness.

    Returns a dict with counts: {degraded: N, offline: N, recovered: N}.
    """
    agents = db.scalars(
        select(CollectorAgent).where(
            CollectorAgent.is_active.is_(True),
            CollectorAgent.status != "retired",
        )
    ).all()

    counts = {"degraded": 0, "offline": 0, "recovered": 0}

    for agent in agents:
        old_status = agent.status
        agent.status = derive_agent_status(agent)

        if old_status != agent.status:
            key = _classify_status_change(old_status, agent.status)
            if key:
                counts[key] += 1
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
    # pylint: disable=import-outside-toplevel
    from sqlalchemy import create_engine  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from internalcmdb.api.config import get_settings  # noqa: PLC0415
    # pylint: enable=import-outside-toplevel

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_staleness_check()
