"""Versioned prompt template governance — load, validate, and version-lock prompt templates.

pt-018 [m5-3] — epic-5 sprint-9.
Manages the lifecycle of PromptTemplateRegistry rows: registration, activation,
deactivation, version-locking, and retrieval.  By convention every call to
`register()` checks that no active template with the same `template_code` already
exists at a *higher* version, preventing accidental downgrades.

Design decisions:
- Version string follows semver-lite: "MAJOR.MINOR.PATCH" — validated at registration.
- Deactivation is soft (is_active = False); templates are never deleted.
- `get_active()` raises KeyError for unknown / inactive codes so callers cannot
  accidentally use a stale template without explicit error handling.
- All mutations call `session.flush()`; the caller is responsible for commit.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from internalcmdb.models.agent_control import PromptTemplateRegistry
from internalcmdb.retrieval.task_types import TaskTypeCode

# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _parse_version(v: str) -> tuple[int, int, int]:
    """Parse "MAJOR.MINOR.PATCH" → (major, minor, patch).  Raises ValueError if invalid."""
    if not _VERSION_RE.match(v):
        msg = f"Invalid version string '{v}'; expected MAJOR.MINOR.PATCH"
        raise ValueError(msg)
    major, minor, patch = v.split(".")
    return int(major), int(minor), int(patch)


# ---------------------------------------------------------------------------
# Public domain types
# ---------------------------------------------------------------------------


@dataclass
class TemplateSpec:
    """Input specification for registering a new prompt template version.

    Attributes:
        template_code: Stable code identifying this template across versions.
        task_type_code: Task type this template targets (TT-001..TT-007).
        template_version: Semver-lite version string, e.g. "1.0.0".
        template_text: Full Jinja2/plain text prompt body.
        policy_record_id: Optional governance policy record binding.
        document_version_id: Optional canonical doc version association.
    """

    template_code: str
    task_type_code: TaskTypeCode
    template_version: str
    template_text: str
    policy_record_id: uuid.UUID | None = None
    document_version_id: uuid.UUID | None = None


@dataclass
class RegistrationResult:
    """Result of a template registration attempt.

    Attributes:
        success: Whether the template was persisted.
        prompt_template_registry_id: UUID of the new row when successful.
        errors: Non-empty only on failure.
        warnings: Non-fatal advisory messages.
    """

    success: bool
    prompt_template_registry_id: uuid.UUID | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Governance engine
# ---------------------------------------------------------------------------


class PromptGovernance:
    """Manages versioned prompt template lifecycle against the DB registry.

    Usage::

        pg = PromptGovernance(session)
        result = pg.register(spec)
        template = pg.get_active("tmpl-svc-audit")
        pg.deactivate("tmpl-svc-audit", "replaced by v2")
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def register(self, spec: TemplateSpec) -> RegistrationResult:
        """Register a new template version.

        Rules:
        - Version string must match MAJOR.MINOR.PATCH.
        - If an active template with the same code exists, its version must be
          strictly lower than the new version (no downgrade, no duplicate).
        - The previous active template is deactivated automatically so that
          `get_active()` always returns a single unambiguous row.
        """
        errors: list[str] = []
        warnings: list[str] = []

        try:
            new_ver = _parse_version(spec.template_version)
        except ValueError as exc:
            return RegistrationResult(success=False, errors=[str(exc)])

        existing = self._find_active(spec.template_code)
        if existing is not None:
            try:
                existing_ver = _parse_version(existing.template_version)
            except ValueError:
                existing_ver = (0, 0, 0)
            if new_ver <= existing_ver:
                errors.append(
                    f"VERSION_DOWNGRADE: existing active version is "
                    f"{existing.template_version}, cannot register {spec.template_version}"
                )
                return RegistrationResult(success=False, errors=errors)
            # Deactivate the previous version
            existing.is_active = False
            warnings.append(
                f"Previous version {existing.template_version} deactivated automatically"
            )

        row = PromptTemplateRegistry(
            template_code=spec.template_code,
            task_type_code=str(spec.task_type_code),
            template_version=spec.template_version,
            template_text=spec.template_text,
            policy_record_id=spec.policy_record_id,
            document_version_id=spec.document_version_id,
            is_active=True,
        )
        self._session.add(row)
        self._session.flush()
        return RegistrationResult(
            success=True,
            prompt_template_registry_id=row.prompt_template_registry_id,
            warnings=warnings,
        )

    def get_active(self, template_code: str) -> PromptTemplateRegistry:
        """Return the active template for *template_code*.

        Raises:
            KeyError: If no active template exists for the given code.
        """
        row = self._find_active(template_code)
        if row is None:
            msg = f"No active prompt template found for code '{template_code}'"
            raise KeyError(msg)
        return row

    def deactivate(self, template_code: str, reason: str) -> bool:
        """Soft-deactivate the active template for *template_code*.

        Returns True if a row was deactivated, False if no active template found.
        """
        row = self._find_active(template_code)
        if row is None:
            return False
        row.is_active = False
        row.updated_at = datetime.now(tz=UTC).isoformat()
        # Store reason in updated_at is not ideal; we annotate via a no-op comment field —
        # the reason is intentionally logged by the caller's audit ledger, not stored here.
        _ = reason  # caller should record via AuditLedger.record_event()
        self._session.flush()
        return True

    def list_versions(self, template_code: str) -> list[PromptTemplateRegistry]:
        """Return all versions (active and inactive) for *template_code*, newest first."""
        rows = (
            self._session.query(PromptTemplateRegistry)
            .filter(PromptTemplateRegistry.template_code == template_code)
            .all()
        )
        return sorted(
            rows,
            key=lambda r: _parse_version_safe(r.template_version),
            reverse=True,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_active(self, template_code: str) -> PromptTemplateRegistry | None:
        rows = (
            self._session.query(PromptTemplateRegistry)
            .filter(
                PromptTemplateRegistry.template_code == template_code,
                PromptTemplateRegistry.is_active.is_(True),
            )
            .limit(1)
            .all()
        )
        if not rows:
            return None
        first = rows[0]
        return first if isinstance(first, PromptTemplateRegistry) else None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_version_safe(v: str) -> tuple[int, int, int]:
    """Parse version without raising; returns (0,0,0) on invalid input."""
    try:
        return _parse_version(v)
    except ValueError:
        return (0, 0, 0)


_MAX_TEMPLATE_CHARS: int = 32_000


def validate_template_text(template_text: str) -> list[str]:
    """Validate prompt template text for common structural issues.

    Returns a list of warning strings (empty means the template is clean).
    The validator is intentionally permissive — it flags suspicious patterns
    without blocking registration.
    """
    warnings: list[str] = []
    if not template_text.strip():
        warnings.append("EMPTY_TEMPLATE: template_text is blank")
    if len(template_text) > _MAX_TEMPLATE_CHARS:
        warnings.append(
            f"LARGE_TEMPLATE: template_text is {len(template_text)} chars; "
            "consider splitting or referencing a document chunk"
        )  # Detect unmatched Jinja2 block delimiters (heuristic)
    if template_text.count("{%") != template_text.count("%}"):
        warnings.append("UNMATCHED_JINJA_BLOCK: '{%' and '%}' counts differ")
    if template_text.count("{{") != template_text.count("}}"):
        warnings.append("UNMATCHED_JINJA_VAR: '{{' and '}}' counts differ")
    return warnings


def build_template_metadata(row: PromptTemplateRegistry) -> dict[str, Any]:
    """Return a serializable metadata dict for a template registry row."""
    return {
        "prompt_template_registry_id": str(row.prompt_template_registry_id),
        "template_code": row.template_code,
        "task_type_code": row.task_type_code,
        "template_version": row.template_version,
        "is_active": row.is_active,
        "policy_record_id": str(row.policy_record_id) if row.policy_record_id else None,
        "document_version_id": (str(row.document_version_id) if row.document_version_id else None),
        "created_at": str(row.created_at),
    }
