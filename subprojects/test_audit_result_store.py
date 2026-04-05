from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Adăugăm subprojects în path pentru import direct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_result_store import (
    MAX_HISTORY_FILES,
    TIMESTAMP_FORMAT,
    _archive_current_file,
    _prune_history,
    _read_archive_stamp,
    build_result_envelope,
    is_local_host,
    write_retained_result,
)


# ---------------------------------------------------------------------------
# build_result_envelope
# ---------------------------------------------------------------------------


def test_build_result_envelope_structure() -> None:
    result = build_result_envelope("test_type", {"key": "value"})
    assert set(result.keys()) == {"result_type", "generated_at_utc", "payload"}
    assert result["result_type"] == "test_type"
    assert result["payload"] == {"key": "value"}


def test_build_result_envelope_timestamp_format() -> None:
    result = build_result_envelope("noop", None)
    ts = result["generated_at_utc"]
    assert isinstance(ts, str)
    # Trebuie să fie parsabil ca ISO 8601
    datetime.fromisoformat(ts.replace("Z", "+00:00"))


def test_build_result_envelope_payload_types() -> None:
    for payload in (None, [], {}, "string", 42, [1, 2, 3]):
        env = build_result_envelope("t", payload)
        assert env["payload"] == payload
        assert env["result_type"] == "t"


# ---------------------------------------------------------------------------
# write_retained_result
# ---------------------------------------------------------------------------


def test_write_retained_result_creates_file(tmp_path: Path) -> None:
    script = tmp_path / "myscript.py"
    script.touch()
    payload = {"data": "hello"}
    current = write_retained_result(script, "my_result", payload)
    assert current.exists()
    content = json.loads(current.read_text())
    assert content == payload


def test_write_retained_result_archives_existing(tmp_path: Path) -> None:
    script = tmp_path / "s.py"
    script.touch()
    old_payload = {"generated_at_utc": "2024-01-15T10:00:00+00:00", "old": True}
    results_dir = tmp_path / "results" / "typ"
    results_dir.mkdir(parents=True)
    current_path = results_dir / "current.json"
    current_path.write_text(json.dumps(old_payload), encoding="utf-8")

    write_retained_result(script, "typ", {"new": True})

    # current.json acum conține noul payload
    new_content = json.loads(current_path.read_text())
    assert new_content == {"new": True}

    # Cel puțin un fișier de arhivă a fost creat
    archive_files = [f for f in results_dir.iterdir() if f.name != "current.json"]
    assert len(archive_files) >= 1


def test_write_retained_result_returns_current_path(tmp_path: Path) -> None:
    script = tmp_path / "s.py"
    script.touch()
    result = write_retained_result(script, "rtype", {"x": 1})
    assert result.name == "current.json"
    assert "rtype" in str(result)


# ---------------------------------------------------------------------------
# _prune_history
# ---------------------------------------------------------------------------


def test_prune_history_keeps_max_two(tmp_path: Path) -> None:
    # Creăm 5 fișiere de arhivă + current.json
    (tmp_path / "current.json").write_text("{}", encoding="utf-8")
    for i in range(5):
        (tmp_path / f"rtype-20240101T0000{i:02d}Z.json").write_text("{}", encoding="utf-8")

    _prune_history(tmp_path)

    archive_files = [f for f in tmp_path.iterdir() if f.name != "current.json"]
    assert len(archive_files) == MAX_HISTORY_FILES


def test_prune_history_keeps_newest(tmp_path: Path) -> None:
    (tmp_path / "current.json").write_text("{}", encoding="utf-8")
    names = [
        "rtype-20240101T000001Z.json",
        "rtype-20240101T000002Z.json",
        "rtype-20240101T000003Z.json",
    ]
    for name in names:
        (tmp_path / name).write_text("{}", encoding="utf-8")

    _prune_history(tmp_path)

    remaining = {f.name for f in tmp_path.iterdir() if f.name != "current.json"}
    # Sortate descrescător → primele 2 = cele mai noi
    assert "rtype-20240101T000003Z.json" in remaining
    assert "rtype-20240101T000002Z.json" in remaining
    assert "rtype-20240101T000001Z.json" not in remaining


def test_prune_history_no_archive_files(tmp_path: Path) -> None:
    (tmp_path / "current.json").write_text("{}", encoding="utf-8")
    _prune_history(tmp_path)
    files = list(tmp_path.iterdir())
    assert len(files) == 1


# ---------------------------------------------------------------------------
# _read_archive_stamp
# ---------------------------------------------------------------------------


def test_read_archive_stamp_from_json(tmp_path: Path) -> None:
    f = tmp_path / "current.json"
    f.write_text(
        json.dumps({"generated_at_utc": "2024-06-15T12:30:00+00:00"}),
        encoding="utf-8",
    )
    stamp = _read_archive_stamp(f)
    assert stamp == "20240615T123000Z"


def test_read_archive_stamp_fallback(tmp_path: Path) -> None:
    f = tmp_path / "current.json"
    f.write_text("not valid json !!!", encoding="utf-8")
    stamp = _read_archive_stamp(f)
    # Fallback la mtime — trebuie să aibă formatul TIMESTAMP_FORMAT
    assert len(stamp) == len("20240615T123000Z")
    datetime.strptime(stamp, TIMESTAMP_FORMAT)


def test_read_archive_stamp_missing_field(tmp_path: Path) -> None:
    f = tmp_path / "current.json"
    f.write_text(json.dumps({"no_timestamp": True}), encoding="utf-8")
    stamp = _read_archive_stamp(f)
    datetime.strptime(stamp, TIMESTAMP_FORMAT)


# ---------------------------------------------------------------------------
# _archive_current_file
# ---------------------------------------------------------------------------


def test_archive_current_file_creates_archive(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    current = results_dir / "current.json"
    content = {"generated_at_utc": "2024-03-20T08:00:00+00:00", "payload": "data"}
    current.write_text(json.dumps(content), encoding="utf-8")

    _archive_current_file(current, results_dir, "mytype")

    archive_files = [f for f in results_dir.iterdir() if f.name != "current.json"]
    assert len(archive_files) == 1
    archived = json.loads(archive_files[0].read_text())
    assert archived["payload"] == "data"


def test_archive_current_file_no_collision(tmp_path: Path) -> None:
    results_dir = tmp_path
    current = results_dir / "current.json"
    ts = "2024-03-20T09:00:00+00:00"
    current.write_text(json.dumps({"generated_at_utc": ts}), encoding="utf-8")

    # Creăm deja un fișier cu același stamp
    stamp = "20240320T090000Z"
    existing = results_dir / f"mytype-{stamp}.json"
    existing.write_text("{}", encoding="utf-8")

    _archive_current_file(current, results_dir, "mytype")

    # Trebuie creat un fișier cu suffix -1
    assert (results_dir / f"mytype-{stamp}-1.json").exists()


# ---------------------------------------------------------------------------
# is_local_host
# ---------------------------------------------------------------------------


def test_is_local_host_hostname_match() -> None:
    with patch("audit_result_store.socket.gethostname", return_value="myserver"):
        assert is_local_host("myserver") is True


def test_is_local_host_substring_match() -> None:
    with patch("audit_result_store.socket.gethostname", return_value="Alexs-iMac.local"):
        assert is_local_host("imac") is True


def test_is_local_host_hostname_no_match_continues_ip_check() -> None:
    with (
        patch("audit_result_store.socket.gethostname", return_value="myserver"),
        patch("audit_result_store._parse_ssh_hostname", return_value=None),
        patch("audit_result_store._local_interface_ips", return_value=frozenset()),
    ):
        result = is_local_host("remotehost")
    assert result is False


def test_is_local_host_ip_intersection_match() -> None:
    with (
        patch("audit_result_store.socket.gethostname", return_value="differenthost"),
        patch("audit_result_store._parse_ssh_hostname", return_value="192.168.1.10"),
        patch(
            "audit_result_store.socket.getaddrinfo",
            return_value=[(None, None, None, None, ("192.168.1.10", 0))],
        ),
        patch(
            "audit_result_store._local_interface_ips",
            return_value=frozenset(["192.168.1.10"]),
        ),
    ):
        assert is_local_host("myalias") is True


def test_is_local_host_no_ssh_config_no_match() -> None:
    with (
        patch("audit_result_store.socket.gethostname", return_value="server1"),
        patch("audit_result_store._parse_ssh_hostname", return_value=None),
        patch("audit_result_store._local_interface_ips", return_value=frozenset(["10.0.0.1"])),
    ):
        assert is_local_host("completelyother") is False
