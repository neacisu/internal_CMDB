"""internalCMDB — Data Access Control (pt-057).

Enforces the DATA-001 data classification access model at query time.

Class B data (observed_fact, chunk_embedding, evidence_pack, action_request,
prompt_template_registry, change_log, document_version) may only be read by
callers with the ``platform_engineering`` role.  All other callers are denied
and the denial is logged.

Public surface::

    from internalcmdb.governance.access_control import DataAccessControl, CallerContext

    ctx = CallerContext(caller_id="agent-run-xyz", roles=frozenset({"platform_engineering"}))
    dac = DataAccessControl(session)
    dac.assert_read_allowed("observed_fact", ctx)  # raises AccessDeniedError if denied
"""

from __future__ import annotations

import uuid as _uuid_mod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from internalcmdb.models.governance import ChangeLog

# ---------------------------------------------------------------------------
# Class → minimum required role mapping (DATA-001 §5)
# ---------------------------------------------------------------------------

#: Tables classified as Class B.  Callers must hold ``platform_engineering``
#: to read these tables through the retrieval broker.
_CLASS_B_TABLES: frozenset[str] = frozenset(
    {
        "observed_fact",
        "chunk_embedding",
        "document_chunk",
        "evidence_pack",
        "evidence_pack_item",
        "agent_run",
        "action_request",
        "prompt_template_registry",
        "change_log",
        "document_version",
    }
)

#: Role required to read Class B data.
_ROLE_PLATFORM_ENGINEERING = "platform_engineering"


# ---------------------------------------------------------------------------
# Caller context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CallerContext:
    """Identifies the caller and their granted roles."""

    caller_id: str
    roles: frozenset[str] = field(default_factory=frozenset)  # pyright: ignore[reportUnknownVariableType]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class AccessDeniedError(PermissionError):
    """Raised when a caller lacks the required role to access classified data."""

    def __init__(self, caller_id: str, table: str, required_role: str) -> None:
        super().__init__(
            f"Access denied: caller '{caller_id}' does not hold role "
            f"'{required_role}' required to read Class B table '{table}'."
        )
        self.caller_id = caller_id
        self.table = table
        self.required_role = required_role


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class DataAccessControl:
    """Enforces DATA-001 access rules and logs denials to ``governance.change_log``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def assert_read_allowed(
        self,
        table_name: str,
        ctx: CallerContext,
    ) -> None:
        """Assert that *ctx* may read *table_name*.

        Raises :class:`AccessDeniedError` and records a denial entry in
        ``governance.change_log`` when access is not permitted.
        """
        if table_name not in _CLASS_B_TABLES:
            # Class A table — no role restriction
            return

        if _ROLE_PLATFORM_ENGINEERING in ctx.roles:
            return

        # Denied — record and raise
        self._record_denial(table_name, ctx)
        raise AccessDeniedError(
            caller_id=ctx.caller_id,
            table=table_name,
            required_role=_ROLE_PLATFORM_ENGINEERING,
        )

    def _record_denial(self, table_name: str, ctx: CallerContext) -> None:
        """Persist a denial entry to ``governance.change_log``."""
        now = datetime.now(tz=UTC)
        code = f"data-ac-deny-{ctx.caller_id}-{table_name}-{now.strftime('%Y%m%d%H%M%S%f')}"
        entry = ChangeLog(
            change_code=code,
            entity_kind_term_id=_nil_uuid(),
            entity_id=_nil_uuid(),
            change_source_text="DataAccessControl",
            change_summary_text=(
                f"Class B access denied: caller='{ctx.caller_id}' "
                f"table='{table_name}' missing role='{_ROLE_PLATFORM_ENGINEERING}'"
            ),
            changed_by=ctx.caller_id,
            changed_at=now.isoformat(),
        )
        self._session.add(entry)
        self._session.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _nil_uuid() -> _uuid_mod.UUID:
    """Return the nil UUID used as a placeholder for non-entity log entries."""
    return _uuid_mod.UUID("00000000-0000-0000-0000-000000000000")
