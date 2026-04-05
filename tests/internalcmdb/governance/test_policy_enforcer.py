"""Tests for governance.policy_enforcer."""
from __future__ import annotations
from unittest.mock import MagicMock
from internalcmdb.governance.policy_enforcer import PolicyCheckResult, PolicyEnforcer, PolicyViolation


def _pol(code="P1", name="P", rules=None):
    p = MagicMock()
    p.policy_code = code
    p.policy_name = name
    p.rules_jsonb = rules or {}
    p.is_active = True
    return p


def _db(policies):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = policies
    return db


def test_no_policies_compliant():
    r = PolicyEnforcer(_db([])).check({"type": "deploy", "target": "prod"})
    assert r.compliant is True and len(r.violations) == 0


def test_blocked_action_violation():
    r = PolicyEnforcer(_db([_pol(rules={"blocked_actions": ["delete"]})])).check({"type": "delete", "target": "h"})
    assert not r.compliant and "blocked" in r.violations[0].reason.lower()


def test_non_blocked_action_passes():
    r = PolicyEnforcer(_db([_pol(rules={"blocked_actions": ["delete"]})])).check({"type": "read", "target": "h"})
    assert r.compliant


def test_requires_approval_no_approval():
    r = PolicyEnforcer(_db([_pol(rules={"requires_approval_for": ["deploy"]})])).check({"type": "deploy", "target": "p"})
    assert not r.compliant and any("approval" in v.reason.lower() for v in r.violations)


def test_requires_approval_with_approval():
    r = PolicyEnforcer(_db([_pol(rules={"requires_approval_for": ["deploy"]})])).check({"type": "deploy", "target": "p", "has_approval": True})
    assert r.compliant


def test_restricted_target_blocks():
    r = PolicyEnforcer(_db([_pol(rules={"restricted_targets": ["prod"]})])).check({"type": "update", "target": "prod"})
    assert not r.compliant and any("restricted" in v.reason.lower() for v in r.violations)


def test_restricted_target_with_override():
    r = PolicyEnforcer(_db([_pol(rules={"restricted_targets": ["prod"]})])).check({"type": "update", "target": "prod", "override": True})
    assert r.compliant


def test_multiple_violations():
    p1 = _pol("P1", "Block Delete", {"blocked_actions": ["delete"]})
    p2 = _pol("P2", "Restrict Prod", {"restricted_targets": ["prod"]})
    r = PolicyEnforcer(_db([p1, p2])).check({"type": "delete", "target": "prod"})
    assert not r.compliant and len(r.violations) >= 2


def test_db_failure_fail_closed():
    db = MagicMock()
    db.query.side_effect = RuntimeError("db unavailable")
    r = PolicyEnforcer(db).check({"type": "deploy", "target": "prod"})
    assert not r.compliant and r.violations[0].policy_code == "SYS-FAIL-CLOSED"


def test_policy_check_result_violations_as_tuple():
    v = PolicyViolation("P1", "Policy", "reason")
    r = PolicyCheckResult(compliant=False, violations=[v])
    assert isinstance(r.violations, tuple) and r.violations[0].policy_code == "P1"


def test_policy_check_result_no_violations():
    r = PolicyCheckResult(compliant=True)
    assert r.violations == ()
