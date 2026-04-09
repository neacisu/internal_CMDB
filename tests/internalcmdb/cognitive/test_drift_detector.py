"""Tests for cognitive.drift_detector."""

from __future__ import annotations

import pytest

from internalcmdb.cognitive.drift_detector import DriftDetector, DriftResult


def _det():
    return DriftDetector()


def test_missing_entity_id():
    r = _det().detect_drift("", {"cpu": "10"}, {"cpu": "10"})
    assert not r.has_drift
    assert r.drift_type == "error"


def test_observed_none():
    r = _det().detect_drift("h1", None, {"cpu": "10"})
    assert not r.has_drift
    assert r.drift_type == "error"


def test_canonical_none():
    r = _det().detect_drift("h1", {"cpu": "10"}, None)
    assert r.has_drift
    assert r.drift_type == "missing_canonical"
    assert "cpu" in r.fields_changed


def test_canonical_empty():
    r = _det().detect_drift("h1", {"cpu": "10"}, {})
    assert r.has_drift
    assert r.drift_type == "missing_canonical"


def test_no_drift():
    r = _det().detect_drift("h1", {"version": "1.0"}, {"version": "1.0"})
    assert not r.has_drift
    assert r.fields_changed == []


def test_no_drift_type_coercion():
    assert not _det().detect_drift("h1", {"port": 22}, {"port": "22"}).has_drift


def test_intentional_drift():
    r = _det().detect_drift(
        "h1", {"version": "2.0", "image": "nginx:2.0"}, {"version": "1.0", "image": "nginx:1.0"}
    )
    assert r.has_drift
    assert r.drift_type == "intentional"


def test_accidental_drift():
    r = _det().detect_drift("h1", {"custom_field": "new"}, {"custom_field": "old"})
    assert r.has_drift
    assert r.drift_type == "accidental"


def test_critical_drift_firewall():
    r = _det().detect_drift("h1", {"firewall_rules": "DROP ALL"}, {"firewall_rules": "ACCEPT"})
    assert r.has_drift
    assert r.drift_type == "critical"


def test_critical_drift_authorized_keys():
    r = _det().detect_drift("h1", {"authorized_keys": "new"}, {"authorized_keys": "old"})
    assert r.has_drift
    assert r.drift_type == "critical"


def test_critical_overrides_intentional():
    r = _det().detect_drift(
        "h1", {"version": "2.0", "root_login": "yes"}, {"version": "1.0", "root_login": "no"}
    )
    assert r.drift_type == "critical"


def test_confidence_between_zero_and_one():
    r = _det().detect_drift(
        "h1", {"firewall_rules": "a", "version": "2"}, {"firewall_rules": "b", "version": "1"}
    )
    assert 0.0 <= r.confidence <= 1.0


def test_explanation_present():
    r = _det().detect_drift("h1", {"version": "2"}, {"version": "1"})
    assert r.explanation
    assert "h1" in r.explanation


def test_explanation_truncates_many_fields():
    obs = {f"field_{i}": f"new_{i}" for i in range(20)}
    can = {f"field_{i}": f"old_{i}" for i in range(20)}
    r = _det().detect_drift("h1", obs, can)
    assert "more field" in r.explanation


def test_values_equal_none_none():
    assert DriftDetector._values_equal(None, None) is True


def test_values_equal_none_value():
    assert DriftDetector._values_equal(None, "x") is False


def test_values_equal_list_tuple():
    assert DriftDetector._values_equal([1, 2], (1, 2)) is True


def test_values_equal_dict_equal():
    assert DriftDetector._values_equal({"a": 1}, {"a": 1}) is True


def test_values_equal_dict_different():
    assert DriftDetector._values_equal({"a": 1}, {"a": 2}) is False


def test_drift_result_frozen():
    r = DriftResult(has_drift=True, drift_type="critical", fields_changed=["a"])
    try:
        r.has_drift = False  # type: ignore[misc]
        pytest.fail("should be frozen")
    except AttributeError, TypeError:
        pass
