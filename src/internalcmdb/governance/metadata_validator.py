"""
Metadata validator for platform documents.

Validates YAML frontmatter in platform Markdown documents against the metadata schema
defined in docs/governance/metadata-schema.md.

Usage:
    python -m internalcmdb.governance.metadata_validator docs/adr/ADR-001-truth-model.md
    python -m internalcmdb.governance.metadata_validator docs/ --strict
    python -m internalcmdb.governance.metadata_validator docs/ --strict --check-db

Exit codes:
    0 — all documents valid
    1 — one or more validation errors
    2 — usage / internal error
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants — must match docs/governance/document-taxonomy.md and
#              docs/governance/metadata-schema.md
# ---------------------------------------------------------------------------

KNOWN_DOC_CLASSES: frozenset[str] = frozenset(
    {
        # Class A — Infrastructure & Operations
        "infra_record",
        "node_record",
        "service_dossier",
        "runbook",
        "incident_record",
        # Class B — Governance & Decisions
        "adr",
        "policy_pack",
        "ownership_matrix",
        "change_template",
        "approval_pattern",
        # Class C — Application Definition
        "product_intent",
        "context_boundary",
        "domain_model",
        "arch_view_pack",
        "service_contract",
        "eng_policy",
        "repo_instructions",
        "verification_spec",
        "evidence_map",
        "research_dossier",
        # Class D — Agent Governance
        "agent_policy",
        "retrieval_policy",
        "prompt_template",
        "task_brief",
        # Class E — Observable Operations
        "operational_declaration",
        "reconciliation_report",
        "data_quality_report",
        "readiness_review",
    }
)

KNOWN_DOMAINS: frozenset[str] = frozenset(
    {
        "platform-foundations",
        "infrastructure",
        "networking",
        "storage",
        "security",
        "observability",
        "discovery",
        "registry",
        "retrieval",
        "agent-control",
        "governance",
        "taxonomy",
        "docs",
        "deployment",
        "postgresql",
        "ai-infrastructure",
        "llm-runtime",
        "shared-services",
        "application",
        "applications",
        "development",
        "operations",
        "compliance",
    }
)

PERMITTED_STATUSES: frozenset[str] = frozenset(
    {"draft", "in-review", "approved", "superseded", "deprecated", "rejected"}
)

PERMITTED_RELATIONS: frozenset[str] = frozenset(
    {"describes", "governs", "references", "evidence_for", "supersedes"}
)

PERMITTED_ROLE_TOKENS: frozenset[str] = frozenset(
    {
        "executive_sponsor",
        "architecture_board",
        "platform_program_manager",
        "platform_architecture_lead",
        "platform_engineering_lead",
        "data_registry_owner",
        "discovery_owner",
        "security_and_policy_owner",
        "sre_observability_owner",
        "domain_owners",
    }
)

# Classes that require at least one binding entry (strict mode)
BINDING_REQUIRED_CLASSES: frozenset[str] = frozenset(
    {
        "infra_record",
        "node_record",
        "service_dossier",
        "runbook",
        "product_intent",
        "operational_declaration",
        "reconciliation_report",
    }
)

MANDATORY_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "doc_class",
    "domain",
    "version",
    "status",
    "created",
    "updated",
    "owner",
)

_VERSION_PATTERN = re.compile(r"^\d+\.\d+$")
_DOC_REF_PATTERN = re.compile(r"\[\[doc:([^\]]+)\]\]")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9]$|^[A-Za-z0-9]$")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------


def _extract_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_text) from a Markdown file.

    Returns ({}, text) if no valid YAML frontmatter block is found.
    Raises yaml.YAMLError if frontmatter is present but malformed.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    data: dict[str, Any] = yaml.safe_load(raw) or {}
    body = text[end + 4 :]
    return data, body


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _check_date(value: Any, field_name: str) -> date | None:
    """Validate a date field and return a date object, or append an error and return None."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None


_MIN_TITLE_LEN: int = 10


def _validate(  # noqa: PLR0912, PLR0915
    path: Path,
    fm: dict[str, Any],
    body: str,
    *,
    strict: bool,
    docs_root: Path | None,
) -> ValidationResult:
    result = ValidationResult(path=path)
    err = result.errors.append
    warn = result.warnings.append

    # ------------------------------------------------------------------
    # Level 1 — Mandatory fields
    # ------------------------------------------------------------------
    for f in MANDATORY_FIELDS:
        if f not in fm or fm[f] is None or fm[f] == "":
            err(f"Missing mandatory field: '{f}'")

    if result.errors:
        # No point continuing without mandatory fields
        return result

    # id
    doc_id: str = str(fm["id"])
    if not _ID_PATTERN.match(doc_id):
        err(f"'id' contains invalid characters or format: '{doc_id}'")

    # title
    title: str = str(fm["title"])
    if len(title) < _MIN_TITLE_LEN:
        err(f"'title' is too short (< 10 chars): '{title}'")

    # doc_class
    doc_class: str = str(fm["doc_class"])
    if doc_class not in KNOWN_DOC_CLASSES:
        err(f"'doc_class' is not a known class token: '{doc_class}'")

    # domain
    domain: str = str(fm["domain"])
    if domain not in KNOWN_DOMAINS:
        err(f"'domain' is not a permitted taxonomy domain: '{domain}'")

    # version
    version_raw = fm.get("version")
    version_str = str(version_raw) if version_raw is not None else ""
    if not _VERSION_PATTERN.match(version_str):
        err(f"'version' must be quoted and match 'N.M' format: '{version_raw}'")

    # status
    status: str = str(fm["status"])
    if status not in PERMITTED_STATUSES:
        err(
            f"'status' is not a permitted value: '{status}'. "
            f"Permitted: {sorted(PERMITTED_STATUSES)}"
        )

    # created / updated
    created = _check_date(fm.get("created"), "created")
    if created is None:
        err(f"'created' must be a YYYY-MM-DD date: '{fm.get('created')}'")

    updated = _check_date(fm.get("updated"), "updated")
    if updated is None:
        err(f"'updated' must be a YYYY-MM-DD date: '{fm.get('updated')}'")

    if created and updated and updated < created:
        err(f"'updated' ({updated}) must be ≥ 'created' ({created})")

    # owner
    owner: str = str(fm.get("owner", ""))
    if owner not in PERMITTED_ROLE_TOKENS and not re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+", owner):
        warn(
            f"'owner' is not a canonical role token: '{owner}'. "
            f"Permitted tokens: {sorted(PERMITTED_ROLE_TOKENS)}"
        )

    # superseded_by ↔ status
    if fm.get("superseded_by") and status != "superseded":
        err("'superseded_by' is set but 'status' is not 'superseded'")

    # binding validation
    bindings = fm.get("binding") or []
    if not isinstance(bindings, list):
        err("'binding' must be a list")
    else:
        for i, b in enumerate(bindings):
            if not isinstance(b, dict):
                err(f"'binding[{i}]' must be a mapping")
                continue
            if "entity_type" not in b:
                err(f"'binding[{i}].entity_type' is required")
            else:
                et: str = str(b["entity_type"])
                if not re.match(r"^[a-z_]+\.[a-z_]+$", et):
                    err(f"'binding[{i}].entity_type' must match 'schema.table': '{et}'")
            if "entity_id" not in b or not b["entity_id"]:
                err(f"'binding[{i}].entity_id' is required and must be non-empty")
            if "relation" not in b:
                err(f"'binding[{i}].relation' is required")
            elif str(b["relation"]) not in PERMITTED_RELATIONS:
                err(
                    f"'binding[{i}].relation' is not permitted: '{b['relation']}'. "
                    f"Permitted: {sorted(PERMITTED_RELATIONS)}"
                )

    # ------------------------------------------------------------------
    # Level 2 — Strict rules
    # ------------------------------------------------------------------
    if strict:
        # approved_by and approved_at required when status == approved
        if status == "approved":
            if not fm.get("approved_by"):
                err("'approved_by' is required when status is 'approved'")
            if not fm.get("approved_at"):
                err("'approved_at' is required when status is 'approved'")

        # tags non-empty
        tags = fm.get("tags") or []
        if not isinstance(tags, list) or len(tags) == 0:
            warn("'tags' is empty or missing — recommended for retrieval quality")

        # binding required for binding-required classes
        if doc_class in BINDING_REQUIRED_CLASSES and not bindings:
            err(f"'binding' is required for doc_class '{doc_class}' but is empty")

        # resolve [[doc:ID]] cross-references
        if docs_root is not None:
            for ref_id in _DOC_REF_PATTERN.findall(body):
                if not _resolve_doc_ref(ref_id.strip(), docs_root):
                    warn(
                        f"Cross-reference [[doc:{ref_id}]] does not resolve to any file "
                        f"under {docs_root}"
                    )

        # resolve related_adrs
        related_adrs = fm.get("related_adrs") or []
        if isinstance(related_adrs, list) and docs_root is not None:
            for adr_id in related_adrs:
                if not _resolve_doc_ref(str(adr_id).strip(), docs_root):
                    warn(f"'related_adrs' entry '{adr_id}' does not resolve to any file")

    return result


def _resolve_doc_ref(ref_id: str, docs_root: Path) -> bool:
    """Return True if any file under docs_root contains ref_id in its stem or name."""
    for md_file in docs_root.rglob("*.md"):
        if ref_id in md_file.stem or ref_id in md_file.name:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_file(
    path: Path,
    *,
    strict: bool = False,
    docs_root: Path | None = None,
) -> ValidationResult:
    """Validate a single Markdown document against the platform metadata schema."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result = ValidationResult(path=path)
        result.errors.append(f"Cannot read file: {exc}")
        return result

    try:
        fm, body = _extract_frontmatter(text)
    except yaml.YAMLError as exc:
        result = ValidationResult(path=path)
        result.errors.append(f"Malformed YAML frontmatter: {exc}")
        return result

    if not fm:
        result = ValidationResult(path=path)
        result.errors.append("No YAML frontmatter block found (expected '---' delimiter)")
        return result

    return _validate(path, fm, body, strict=strict, docs_root=docs_root)


def validate_directory(
    directory: Path,
    *,
    strict: bool = False,
    docs_root: Path | None = None,
) -> list[ValidationResult]:
    """Recursively validate all .md files in a directory."""
    results: list[ValidationResult] = []
    for md_file in sorted(directory.rglob("*.md")):
        results.append(validate_file(md_file, strict=strict, docs_root=docs_root))
    return results


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _print_result(result: ValidationResult, *, verbose: bool) -> None:
    status_label = "✓ PASS" if result.is_valid else "✗ FAIL"
    has_warnings = bool(result.warnings)

    if not result.is_valid or has_warnings or verbose:
        print(f"{status_label}  {result.path}")

    for error in result.errors:
        print(f"       ERROR: {error}")

    for warning in result.warnings:
        print(f"       WARN:  {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate platform document metadata (frontmatter) against schema v1.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to a .md file or a directory to validate recursively.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict validation (approved_by, binding requirements, ref resolution).",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help=(
            "Resolve entity_id values against the live internalCMDB database (not yet implemented)."
        ),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help=(
            "Root of the docs tree for cross-reference resolution."
            " Defaults to target if it is a dir."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print all results, including passing files.",
    )
    args = parser.parse_args(argv)

    target: Path = args.target.resolve()
    docs_root: Path | None = args.docs_root

    if target.is_dir() and docs_root is None and args.strict:
        docs_root = target

    if not target.exists():
        print(f"ERROR: target does not exist: {target}", file=sys.stderr)
        return 2

    if target.is_file():
        results = [validate_file(target, strict=args.strict, docs_root=docs_root)]
    else:
        results = validate_directory(target, strict=args.strict, docs_root=docs_root)

    if not results:
        print("No .md files found.")
        return 0

    fail_count = 0
    warn_count = 0
    for result in results:
        _print_result(result, verbose=args.verbose)
        if not result.is_valid:
            fail_count += 1
        if result.warnings:
            warn_count += len(result.warnings)

    total = len(results)
    passed = total - fail_count
    print(f"\n{'─' * 60}")
    print(
        f"Validated {total} document(s): {passed} passed, {fail_count} failed, "
        f"{warn_count} warning(s)."
    )

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
