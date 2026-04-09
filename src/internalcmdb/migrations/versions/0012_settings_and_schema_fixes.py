"""Settings schema + critical schema fixes.

Revision ID: 0012
Revises: 0011
Created: 2026-04-04

Fixes two pre-existing runtime blockers:
  1. cognitive.self_heal_action  — referenced by cognitive_tasks.py but never created
  2. cognitive.insight.evidence  — INSERT column referenced by cognitive_tasks.py but missing

New config schema:
  config.app_setting            — runtime-configurable key/value settings (DB-backed)
  config.notification_channel   — outbound webhook notification channels
  config.user_preference        — per-user UI preferences
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COGNITIVE = "cognitive"
_CONFIG = "config"


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # FIX 1: cognitive.self_heal_action
    # Referenced in workers/cognitive_tasks.py + api/routers/cognitive.py
    # but never included in migrations 0001-0011.
    # -----------------------------------------------------------------------
    op.execute(
        sa.text(f"""
            CREATE TABLE IF NOT EXISTS {_COGNITIVE}.self_heal_action (
                action_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                playbook_name   TEXT NOT NULL,
                entity_id       TEXT,
                status          TEXT NOT NULL DEFAULT 'completed'
                                    CHECK (status IN ('completed', 'failed', 'skipped')),
                result_summary  TEXT,
                executed_by     TEXT NOT NULL DEFAULT 'cognitive_self_heal',
                executed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_self_heal_action_entity "
            f"ON {_COGNITIVE}.self_heal_action (entity_id)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_self_heal_action_executed_at "
            f"ON {_COGNITIVE}.self_heal_action (executed_at DESC)"
        )
    )
    op.execute(
        sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_self_heal_action_playbook "
            f"ON {_COGNITIVE}.self_heal_action (playbook_name, executed_at DESC)"
        )
    )

    # -----------------------------------------------------------------------
    # FIX 2: cognitive.insight — add missing 'evidence' column
    # cognitive_tasks.py inserts: :evidence::jsonb
    # -----------------------------------------------------------------------
    op.execute(
        sa.text(
            f"ALTER TABLE {_COGNITIVE}.insight "
            f"ADD COLUMN IF NOT EXISTS evidence JSONB NOT NULL DEFAULT '[]'::jsonb"
        )
    )

    # -----------------------------------------------------------------------
    # NEW: config schema + tables
    # -----------------------------------------------------------------------
    op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {_CONFIG}"))

    # config.app_setting — runtime key/value store, DB-backed, cacheable
    op.execute(
        sa.text(f"""
            CREATE TABLE {_CONFIG}.app_setting (
                setting_key      TEXT PRIMARY KEY,
                setting_group    TEXT NOT NULL,
                value_jsonb      JSONB NOT NULL,
                default_jsonb    JSONB NOT NULL,
                type_hint        TEXT NOT NULL DEFAULT 'string'
                                     CHECK (type_hint IN (
                                         'string', 'integer', 'float',
                                         'boolean', 'url', 'secret', 'json_array'
                                     )),
                description      TEXT,
                is_secret        BOOLEAN NOT NULL DEFAULT false,
                requires_restart BOOLEAN NOT NULL DEFAULT false,
                updated_at       TIMESTAMPTZ,
                updated_by       TEXT
            )
        """)
    )
    op.execute(
        sa.text(f"CREATE INDEX ix_app_setting_group ON {_CONFIG}.app_setting (setting_group)")
    )

    # config.notification_channel — outbound webhook channels
    # hmac_secret_hash stores SHA-256 hex of the caller's shared secret (OWASP A02)
    op.execute(
        sa.text(f"""
            CREATE TABLE {_CONFIG}.notification_channel (
                channel_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name             TEXT NOT NULL,
                channel_type     TEXT NOT NULL DEFAULT 'webhook'
                                     CHECK (channel_type IN ('webhook')),
                target_url       TEXT,
                hmac_secret_hash TEXT,
                events           TEXT[] NOT NULL DEFAULT '{{}}',
                is_active        BOOLEAN NOT NULL DEFAULT true,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    )
    op.execute(
        sa.text(
            f"CREATE INDEX ix_notification_channel_active "
            f"ON {_CONFIG}.notification_channel (is_active) WHERE is_active = true"
        )
    )

    # config.user_preference — per-user UI preferences
    op.execute(
        sa.text(f"""
            CREATE TABLE {_CONFIG}.user_preference (
                preference_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id        TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                value_jsonb    JSONB NOT NULL,
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                CONSTRAINT uq_user_preference UNIQUE (user_id, preference_key)
            )
        """)
    )
    op.execute(
        sa.text(f"CREATE INDEX ix_user_preference_user ON {_CONFIG}.user_preference (user_id)")
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_CONFIG}.user_preference"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_CONFIG}.notification_channel"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_CONFIG}.app_setting"))
    op.execute(sa.text(f"DROP SCHEMA IF EXISTS {_CONFIG}"))
    op.execute(sa.text(f"ALTER TABLE {_COGNITIVE}.insight DROP COLUMN IF EXISTS evidence"))
    op.execute(sa.text(f"DROP TABLE IF EXISTS {_COGNITIVE}.self_heal_action"))
