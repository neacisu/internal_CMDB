"""Tests for internalcmdb.governance.metadata_validator (pt-validation).

Covers:
- validate_file: missing mandatory fields → errors
- validate_file: malformed YAML frontmatter → error
- validate_file: no frontmatter block → error
- validate_file: invalid doc_class → error
- validate_file: invalid domain → error
- validate_file: invalid version format → error
- validate_file: invalid status → error
- validate_file: invalid date format → error
- validate_file: updated < created → error
- validate_file: superseded_by without status=superseded → error
- validate_file: invalid binding.entity_type format → error
- validate_file: invalid binding.relation → error
- validate_file: valid minimal doc → no errors
- validate_file: valid complete doc → is_valid=True
- strict: approved status without approved_by → error
- strict: binding required class without binding → error
- validate_directory: processes all .md files recursively
- validate_directory: empty directory → empty results
- ValidationResult.is_valid
"""

from __future__ import annotations

# pylint: disable=redefined-outer-name
from pathlib import Path
from textwrap import dedent

import pytest

from internalcmdb.governance.metadata_validator import (  # pylint: disable=import-error
    BINDING_REQUIRED_CLASSES,
    KNOWN_DOC_CLASSES,
    KNOWN_DOMAINS,
    PERMITTED_STATUSES,
    ValidationResult,
    main,
    validate_directory,
    validate_file,
)

# ---------------------------------------------------------------------------
# Minimal valid frontmatter for reuse
# ---------------------------------------------------------------------------

_VALID_FM = dedent("""\
    ---
    id: TEST-001
    title: Test Document for Unit Testing
    doc_class: adr
    domain: governance
    version: "1.0"
    status: draft
    created: 2025-01-01
    updated: 2025-06-01
    owner: platform_engineering_lead
    ---
    # Test document body
""")

_VALID_MINIMAL_FM = dedent("""\
    ---
    id: SVC-001
    title: Test Infrastructure Document
    doc_class: runbook
    domain: infrastructure
    version: "1.0"
    status: draft
    created: 2025-01-01
    updated: 2025-06-01
    owner: sre_observability_owner
    ---
    Body text here.
""")


def _write_md(content: str, directory: Path, name: str = "test.md") -> Path:
    p = directory / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_docs(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Valid documents
# ---------------------------------------------------------------------------


class TestValidDocuments:
    def test_minimal_valid_doc_is_valid(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        result = validate_file(p)
        assert result.is_valid, f"Unexpected errors: {result.errors}"

    def test_is_valid_property_true(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        result = validate_file(p)
        assert result.is_valid is True

    def test_no_errors_on_valid_doc(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        result = validate_file(p)
        assert result.errors == []


# ---------------------------------------------------------------------------
# Missing mandatory fields
# ---------------------------------------------------------------------------


class TestMissingMandatoryFields:
    @pytest.mark.parametrize(
        "field_to_remove",
        ["id", "title", "doc_class", "domain", "version", "status", "created", "updated", "owner"],
    )
    def test_missing_field_triggers_error(self, tmp_docs: Path, field_to_remove: str) -> None:
        fm = dedent("""\
            ---
            id: T-001
            title: Long enough title here
            doc_class: adr
            domain: governance
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: security_and_policy_owner
            ---
            Body.
        """)
        # Remove the line for the specific field
        lines = fm.splitlines(keepends=True)
        filtered = "".join(
            line for line in lines if not line.strip().startswith(f"{field_to_remove}:")
        )
        p = _write_md(filtered, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any(field_to_remove in e for e in result.errors)


# ---------------------------------------------------------------------------
# No frontmatter
# ---------------------------------------------------------------------------


class TestNoFrontmatter:
    def test_missing_frontmatter_gives_error(self, tmp_docs: Path) -> None:
        p = _write_md("# Just a heading\n\nSome body text.", tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("frontmatter" in e.lower() or "No YAML" in e for e in result.errors)

    def test_malformed_yaml_gives_error(self, tmp_docs: Path) -> None:
        malformed = "---\ntitle: [unclosed bracket\n---\nBody."
        p = _write_md(malformed, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("YAML" in e or "frontmatter" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Invalid field values
# ---------------------------------------------------------------------------


class TestInvalidFieldValues:
    def test_invalid_doc_class_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("doc_class: adr", "doc_class: nonexistent_class")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("doc_class" in e for e in result.errors)

    def test_invalid_domain_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("domain: governance", "domain: totally-unknown-domain")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("domain" in e for e in result.errors)

    def test_invalid_version_format_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace('version: "1.0"', "version: 1")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("version" in e for e in result.errors)

    def test_invalid_status_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("status: draft", "status: unknown_status")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("status" in e for e in result.errors)

    def test_invalid_created_date_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("created: 2025-01-01", "created: not-a-date")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("created" in e for e in result.errors)

    def test_updated_before_created_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("updated: 2025-06-01", "updated: 2024-01-01")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("updated" in e for e in result.errors)

    def test_short_title_gives_error(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("title: Test Document for Unit Testing", "title: Short")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("title" in e for e in result.errors)


# ---------------------------------------------------------------------------
# superseded_by
# ---------------------------------------------------------------------------


class TestSupersededBy:
    def test_superseded_by_without_superseded_status_fails(self, tmp_docs: Path) -> None:
        # superseded_by inside the frontmatter with status=draft -> error
        fm = dedent("""\
            ---
            id: T-SUPER-FAIL
            title: Superseded Document Without Matching Status
            doc_class: adr
            domain: governance
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: platform_engineering_lead
            superseded_by: OTHER-001
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("superseded_by" in e for e in result.errors)

    def test_superseded_by_with_superseded_status_ok(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-SUPER
            title: Superseded Document Title Here
            doc_class: adr
            domain: governance
            version: "2.0"
            status: superseded
            created: 2024-01-01
            updated: 2025-01-01
            owner: platform_engineering_lead
            superseded_by: T-SUPER-V2
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert result.is_valid, f"Unexpected errors: {result.errors}"


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class TestBindings:
    def test_invalid_entity_type_format_gives_error(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-BIND
            title: Document with binding issues here
            doc_class: adr
            domain: governance
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: platform_engineering_lead
            binding:
              - entity_type: invalid_no_dot
                entity_id: some-id
                relation: describes
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("entity_type" in e for e in result.errors)

    def test_invalid_relation_gives_error(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-BIND2
            title: Document with invalid relation binding
            doc_class: adr
            domain: governance
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: platform_engineering_lead
            binding:
              - entity_type: registry.host
                entity_id: abc-123
                relation: invalid_relation
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert not result.is_valid
        assert any("relation" in e for e in result.errors)

    def test_valid_binding_passes(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-BIND3
            title: Document with valid binding entry here
            doc_class: adr
            domain: governance
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: platform_engineering_lead
            binding:
              - entity_type: registry.host
                entity_id: abc-123-def
                relation: describes
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        assert result.is_valid, f"Unexpected errors: {result.errors}"


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


class TestStrictMode:
    def test_approved_without_approved_by_fails_strict(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-STRICT
            title: Document that needs approved by field
            doc_class: adr
            domain: governance
            version: "1.0"
            status: approved
            created: 2025-01-01
            updated: 2025-06-01
            owner: architecture_board
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p, strict=True)
        assert not result.is_valid
        assert any("approved_by" in e for e in result.errors)

    def test_approved_with_approved_by_and_approved_at_passes_strict(self, tmp_docs: Path) -> None:
        fm = dedent("""\
            ---
            id: T-IS-APPROVED
            title: Document That Is Properly Approved Here
            doc_class: adr
            domain: governance
            version: "1.0"
            status: approved
            created: 2025-01-01
            updated: 2025-06-01
            owner: architecture_board
            approved_by: Alice Smith
            approved_at: 2025-06-01
            ---
            Body.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p, strict=True)
        assert result.is_valid, f"Errors: {result.errors}"

    def test_binding_required_class_without_binding_fails_strict(self, tmp_docs: Path) -> None:
        # runbook requires binding in strict mode
        fm = dedent("""\
            ---
            id: T-STRICT2
            title: Runbook with No Binding Entry at All
            doc_class: runbook
            domain: infrastructure
            version: "1.0"
            status: draft
            created: 2025-01-01
            updated: 2025-06-01
            owner: sre_observability_owner
            ---
            Body text here.
        """)
        p = _write_md(fm, tmp_docs)
        result = validate_file(p, strict=True)
        assert not result.is_valid
        assert any("binding" in e for e in result.errors)


# ---------------------------------------------------------------------------
# validate_directory
# ---------------------------------------------------------------------------


class TestValidateDirectory:
    def test_empty_directory_returns_empty_list(self, tmp_docs: Path) -> None:
        results = validate_directory(tmp_docs)
        assert results == []

    def test_single_md_file_returns_one_result(self, tmp_docs: Path) -> None:
        _write_md(_VALID_FM, tmp_docs)
        results = validate_directory(tmp_docs)
        assert len(results) == 1

    def test_multiple_md_files_returns_all(self, tmp_docs: Path) -> None:
        _write_md(_VALID_FM, tmp_docs, "a.md")
        _write_md(_VALID_MINIMAL_FM, tmp_docs, "b.md")
        results = validate_directory(tmp_docs)
        assert len(results) == 2

    def test_recursive_subdirectory_discovered(self, tmp_docs: Path) -> None:
        sub = tmp_docs / "sub"
        sub.mkdir()
        _write_md(_VALID_FM, sub, "nested.md")
        results = validate_directory(tmp_docs)
        assert len(results) == 1
        assert results[0].path.name == "nested.md"

    def test_non_md_files_not_included(self, tmp_docs: Path) -> None:
        (tmp_docs / "notes.txt").write_text("plain text")
        results = validate_directory(tmp_docs)
        assert results == []

    def test_invalid_file_returns_errors(self, tmp_docs: Path) -> None:
        _write_md("# No frontmatter", tmp_docs, "bad.md")
        results = validate_directory(tmp_docs)
        assert len(results) == 1
        assert not results[0].is_valid


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_no_errors_is_valid(self, tmp_docs: Path) -> None:
        r = ValidationResult(path=tmp_docs / "x.md")
        assert r.is_valid is True

    def test_with_error_not_valid(self, tmp_docs: Path) -> None:
        r = ValidationResult(path=tmp_docs / "x.md")
        r.errors.append("some error")
        assert r.is_valid is False

    def test_warnings_do_not_affect_is_valid(self, tmp_docs: Path) -> None:
        r = ValidationResult(path=tmp_docs / "x.md")
        r.warnings.append("a warning")
        assert r.is_valid is True


# ---------------------------------------------------------------------------
# File not found
# ---------------------------------------------------------------------------


class TestFileNotFound:
    def test_nonexistent_file_returns_error(self, tmp_docs: Path) -> None:
        result = validate_file(tmp_docs / "does_not_exist.md")
        assert not result.is_valid
        assert any("Cannot read" in e or "not" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_known_doc_classes_not_empty(self) -> None:
        assert len(KNOWN_DOC_CLASSES) > 0

    def test_adr_is_known_doc_class(self) -> None:
        assert "adr" in KNOWN_DOC_CLASSES

    def test_runbook_is_known_doc_class(self) -> None:
        assert "runbook" in KNOWN_DOC_CLASSES

    def test_known_domains_not_empty(self) -> None:
        assert len(KNOWN_DOMAINS) > 0

    def test_governance_is_known_domain(self) -> None:
        assert "governance" in KNOWN_DOMAINS

    def test_permitted_statuses_has_draft(self) -> None:
        assert "draft" in PERMITTED_STATUSES

    def test_permitted_statuses_has_approved(self) -> None:
        assert "approved" in PERMITTED_STATUSES

    def test_binding_required_classes_not_empty(self) -> None:
        assert len(BINDING_REQUIRED_CLASSES) > 0

    def test_runbook_is_binding_required(self) -> None:
        assert "runbook" in BINDING_REQUIRED_CLASSES


# ---------------------------------------------------------------------------
# main() CLI — exit codes
# ---------------------------------------------------------------------------


class TestMainCli:
    def test_valid_file_exits_zero(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        exit_code = main([str(p)])
        assert exit_code == 0

    def test_invalid_file_exits_one(self, tmp_docs: Path) -> None:
        p = _write_md("# No frontmatter at all", tmp_docs)
        exit_code = main([str(p)])
        assert exit_code == 1

    def test_nonexistent_path_exits_two(self, tmp_docs: Path) -> None:
        exit_code = main([str(tmp_docs / "does_not_exist.md")])
        assert exit_code == 2

    def test_empty_directory_exits_zero(self, tmp_docs: Path) -> None:
        exit_code = main([str(tmp_docs)])
        assert exit_code == 0

    def test_valid_directory_exits_zero(self, tmp_docs: Path) -> None:
        _write_md(_VALID_FM, tmp_docs, "doc.md")
        exit_code = main([str(tmp_docs)])
        assert exit_code == 0

    def test_directory_with_invalid_exits_one(self, tmp_docs: Path) -> None:
        _write_md("# No frontmatter", tmp_docs, "bad.md")
        exit_code = main([str(tmp_docs)])
        assert exit_code == 1

    def test_strict_mode_valid_draft_exits_zero(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        exit_code = main([str(p), "--strict"])
        assert exit_code == 0

    def test_verbose_flag_accepted(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        exit_code = main([str(p), "--verbose"])
        assert exit_code == 0

    def test_docs_root_flag_accepted(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        exit_code = main([str(p), "--docs-root", str(tmp_docs)])
        assert exit_code == 0


# ---------------------------------------------------------------------------
# Owner validation
# ---------------------------------------------------------------------------


class TestOwnerValidation:
    def test_non_canonical_owner_generates_warning(self, tmp_docs: Path) -> None:
        fm = _VALID_FM.replace("owner: platform_engineering_lead", "owner: unknown-owner-xyz")
        p = _write_md(fm, tmp_docs)
        result = validate_file(p)
        # Non-canonical owner generates a warning (not an error)
        assert any("owner" in w for w in result.warnings)

    def test_canonical_owner_no_warning(self, tmp_docs: Path) -> None:
        p = _write_md(_VALID_FM, tmp_docs)
        result = validate_file(p)
        assert not any("owner" in w for w in result.warnings)
