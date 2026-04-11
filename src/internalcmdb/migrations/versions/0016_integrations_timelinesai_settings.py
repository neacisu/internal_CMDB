"""Seed config.app_setting rows for TimelinesAI integration.

Revision ID: 0016
Revises: 0015
Created: 2026-04-11

Adds the setting keys required by the integrations.timelinesai.* router
so that SettingsStore.set() (UPDATE-only) has rows to update.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONFIG = "config"


def upgrade() -> None:
    op.execute(
        sa.text(f"""
            INSERT INTO {_CONFIG}.app_setting
                (setting_key, setting_group, value_jsonb, default_jsonb, type_hint, description, is_secret, requires_restart)
            VALUES
                ('integrations.timelinesai.enabled',          'integrations', 'false',           'false',           'boolean',    'Enable TimelinesAI WhatsApp integration',         false, false),
                ('integrations.timelinesai.api_token',        'integrations', '""',              '""',              'secret',     'TimelinesAI Public API Bearer token',             true,  false),
                ('integrations.timelinesai.webhook_secret',   'integrations', '""',              '""',              'secret',     'HMAC-SHA256 secret for webhook signature validation', true, false),
                ('integrations.timelinesai.subscribed_events','integrations', '["message:received:new"]', '["message:received:new"]', 'json_array', 'Webhook event types to process', false, false),
                ('integrations.timelinesai.auto_reply_enabled','integrations','false',           'false',           'boolean',    'Send auto-reply on new incoming messages',        false, false),
                ('integrations.timelinesai.auto_reply_template','integrations','""',             '""',              'string',     'Auto-reply message template',                    false, false)
            ON CONFLICT (setting_key) DO NOTHING
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
            DELETE FROM {_CONFIG}.app_setting
             WHERE setting_key LIKE 'integrations.timelinesai.%'
        """)
    )
