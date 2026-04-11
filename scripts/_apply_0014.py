"""Apply 0014 migration tables directly (no Alembic)."""

import os

import sqlalchemy as sa

engine = sa.create_engine(
    f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ.get('POSTGRES_SYNC_HOST', '127.0.0.1')}"
    f":{os.environ.get('POSTGRES_SYNC_PORT', '5432')}"
    f"/{os.environ['POSTGRES_DB']}?sslmode=disable"
)

with engine.begin() as conn:
    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS agent_control.command_log ("
            "command_id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,"
            "agent_id UUID NOT NULL,"
            "command_type VARCHAR(64) NOT NULL,"
            "payload JSON NOT NULL,"
            "result JSON,"
            "status VARCHAR(32) DEFAULT 'pending' NOT NULL,"
            "issued_by VARCHAR(128) NOT NULL,"
            "approved_by VARCHAR(128),"
            "hitl_item_id UUID,"
            "error TEXT,"
            "duration_ms INTEGER,"
            "created_at TIMESTAMPTZ DEFAULT now() NOT NULL,"
            "completed_at TIMESTAMPTZ,"
            "expires_at TIMESTAMPTZ)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_command_log_agent_status "
            "ON agent_control.command_log (agent_id, status)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_command_log_created "
            "ON agent_control.command_log (created_at)"
        )
    )
    print("command_log: OK")

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS agent_control.tool_definition ("
            "tool_id VARCHAR(128) NOT NULL PRIMARY KEY,"
            "name VARCHAR(256) NOT NULL,"
            "description TEXT NOT NULL,"
            "parameters_schema JSON NOT NULL,"
            "risk_class VARCHAR(8) NOT NULL,"
            "is_active BOOLEAN DEFAULT true NOT NULL,"
            "tags TEXT[] DEFAULT '{}' NOT NULL,"
            "cooldown_s INTEGER DEFAULT 0 NOT NULL,"
            "created_at TIMESTAMPTZ DEFAULT now() NOT NULL,"
            "updated_at TIMESTAMPTZ)"
        )
    )
    print("tool_definition: OK")

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS agent_control.tool_execution_log ("
            "audit_id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,"
            "tool_id VARCHAR(128) NOT NULL,"
            "session_id UUID,"
            "params JSON NOT NULL,"
            "result JSON,"
            "success BOOLEAN NOT NULL,"
            "error TEXT,"
            "execution_time_ms INTEGER,"
            "risk_class VARCHAR(8) NOT NULL,"
            "triggered_by VARCHAR(128) NOT NULL,"
            "created_at TIMESTAMPTZ DEFAULT now() NOT NULL)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_tool_execution_log_tool "
            "ON agent_control.tool_execution_log (tool_id)"
        )
    )
    print("tool_execution_log: OK")

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS cognitive.agent_session ("
            "session_id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,"
            "goal TEXT NOT NULL,"
            "status VARCHAR(32) DEFAULT 'running' NOT NULL,"
            "model_used VARCHAR(128),"
            "iterations INTEGER DEFAULT 0 NOT NULL,"
            "tokens_used INTEGER DEFAULT 0 NOT NULL,"
            "tool_calls JSON DEFAULT '[]'::json NOT NULL,"
            "conversation JSON DEFAULT '[]'::json NOT NULL,"
            "final_answer TEXT,"
            "error TEXT,"
            "triggered_by VARCHAR(128) NOT NULL,"
            "created_at TIMESTAMPTZ DEFAULT now() NOT NULL,"
            "completed_at TIMESTAMPTZ)"
        )
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_agent_session_status ON cognitive.agent_session (status)"
        )
    )
    print("agent_session: OK")

print("All 0014 migration tables created successfully")
