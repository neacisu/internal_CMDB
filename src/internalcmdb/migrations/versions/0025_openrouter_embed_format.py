"""OpenRouter migration settings — embed API format and model descriptions.

Revision ID: 0025
Revises: 0024
Created: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO config.app_setting
                (setting_key, setting_group, value_jsonb, default_jsonb, type_hint,
                 description, is_secret, requires_restart)
            VALUES
                ('llm.embed.api_format', 'llm', '"openai"', '"openai"', 'string',
                 'Embedding API format: openai (/v1/embeddings) or ollama (/api/embed)',
                 false, false)
            ON CONFLICT (setting_key) DO UPDATE SET
                default_jsonb = EXCLUDED.default_jsonb,
                description = EXCLUDED.description
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE config.app_setting SET description =
                'Reasoning endpoint (HAProxy VIP → LiteLLM → OpenRouter deepseek-v4-pro)'
             WHERE setting_key = 'llm.reasoning.url'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE config.app_setting SET description =
                'Fast endpoint (HAProxy VIP → LiteLLM → OpenRouter deepseek-v4-flash)'
             WHERE setting_key = 'llm.fast.url'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE config.app_setting SET description =
                'Embed endpoint (HAProxy VIP → LiteLLM → OpenRouter qwen3-embedding-8b)'
             WHERE setting_key = 'llm.embed.url'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM config.app_setting WHERE setting_key = 'llm.embed.api_format'
            """
        )
    )
