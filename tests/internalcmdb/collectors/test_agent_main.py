"""Tests for internalcmdb.collectors.agent.__main__ — entrypoint.

Covers:
- ``_load_config()``: TOML loading, AGENT_CONFIG env override, DEFAULT_CONFIG_PATHS
- ``main()``: daemon config derivation (env > TOML > hardcoded defaults), verify_ssl
  truthiness semantics, non-HTTPS warning, event-loop lifecycle, signal handling,
  KeyboardInterrupt recovery.
"""

from __future__ import annotations

import importlib
import signal as _signal_mod
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

_MODULE = "internalcmdb.collectors.agent.__main__"


def _mod():
    """Return the (cached) __main__ module."""
    return importlib.import_module(_MODULE)


def _make_loop() -> MagicMock:
    """Return a mock event loop with sensible defaults."""
    loop = MagicMock()
    loop.run_until_complete.return_value = None
    loop.create_task.return_value = MagicMock()
    return loop


def _run_main(
    *,
    env: dict[str, str] | None = None,
    config: dict[str, object] | None = None,
    loop: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Run ``main()`` with all real I/O mocked.

    Returns ``(daemon_cls, daemon_instance, mock_loop)`` so callers can
    inspect what the entrypoint passed to ``AgentDaemon``.
    """
    mod = _mod()
    mock_loop = loop if loop is not None else _make_loop()

    daemon_cls = MagicMock()
    daemon_instance = MagicMock()
    daemon_cls.return_value = daemon_instance

    mock_asyncio = MagicMock()
    mock_asyncio.new_event_loop.return_value = mock_loop

    # Keep real signal constants so signal-handler tests can verify by value.
    mock_signal = MagicMock()
    mock_signal.SIGTERM = _signal_mod.SIGTERM
    mock_signal.SIGINT = _signal_mod.SIGINT

    with (
        patch.object(mod, "_load_config", return_value=config if config is not None else {}),
        patch.object(mod, "AgentDaemon", daemon_cls),
        patch(f"{_MODULE}.asyncio", mock_asyncio),
        patch(f"{_MODULE}.signal", mock_signal),
        patch.dict("os.environ", env if env is not None else {}, clear=True),
    ):
        mod.main()

    return daemon_cls, daemon_instance, mock_loop


# ---------------------------------------------------------------------------
# _load_config()
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Unit tests for the TOML config loader."""

    def test_no_config_files_returns_empty_dict(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.delenv("AGENT_CONFIG", raising=False)

        with patch.object(mod.os.path, "isfile", return_value=False):
            result = mod._load_config()

        assert result == {}

    def test_env_var_config_path_used_when_set(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.setenv("AGENT_CONFIG", "/custom/path.toml")
        fake_toml: dict[str, object] = {"agent": {"api_url": "https://example.com"}}

        with (
            patch.object(mod.os.path, "isfile", return_value=True),
            patch("builtins.open", MagicMock()),
            patch.object(mod.tomllib, "load", return_value=fake_toml),
        ):
            result = mod._load_config()

        assert result == fake_toml

    def test_env_var_searches_only_custom_path(self, monkeypatch: pytest.MonkeyPatch):
        """When ``AGENT_CONFIG`` is set, only that path is tried (not the defaults)."""
        mod = _mod()
        monkeypatch.setenv("AGENT_CONFIG", "/custom/path.toml")
        checked: list[str] = []

        def _isfile(p: str) -> bool:
            checked.append(p)
            return False

        with patch.object(mod.os.path, "isfile", side_effect=_isfile):
            mod._load_config()

        assert checked == ["/custom/path.toml"]

    def test_default_paths_searched_without_env_var(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.delenv("AGENT_CONFIG", raising=False)
        checked: list[str] = []

        def _isfile(p: str) -> bool:
            checked.append(p)
            return False

        with patch.object(mod.os.path, "isfile", side_effect=_isfile):
            mod._load_config()

        assert checked == mod.DEFAULT_CONFIG_PATHS

    def test_first_existing_path_wins(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.delenv("AGENT_CONFIG", raising=False)
        paths = mod.DEFAULT_CONFIG_PATHS
        fake_toml: dict[str, object] = {"agent": {"host_code": "from-second-path"}}

        def _isfile(p: str) -> bool:
            return p == paths[1]

        with (
            patch.object(mod.os.path, "isfile", side_effect=_isfile),
            patch("builtins.open", MagicMock()),
            patch.object(mod.tomllib, "load", return_value=fake_toml),
        ):
            result = mod._load_config()

        assert result is fake_toml

    def test_toml_content_returned_verbatim(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.delenv("AGENT_CONFIG", raising=False)
        fake_toml: dict[str, object] = {
            "agent": {"api_url": "https://x.y", "log_level": "DEBUG"},
            "meta": {"version": 2},
        }

        with (
            patch.object(mod.os.path, "isfile", return_value=True),
            patch("builtins.open", MagicMock()),
            patch.object(mod.tomllib, "load", return_value=fake_toml),
        ):
            result = mod._load_config()

        assert result["agent"] == {"api_url": "https://x.y", "log_level": "DEBUG"}  # type: ignore[index]
        assert result["meta"] == {"version": 2}  # type: ignore[index]

    def test_empty_env_var_falls_back_to_default_paths(self, monkeypatch: pytest.MonkeyPatch):
        """Empty string for AGENT_CONFIG is falsy — default paths should be used."""
        mod = _mod()
        monkeypatch.setenv("AGENT_CONFIG", "")
        checked: list[str] = []

        def _isfile(p: str) -> bool:
            checked.append(p)
            return False

        with patch.object(mod.os.path, "isfile", side_effect=_isfile):
            mod._load_config()

        assert checked == mod.DEFAULT_CONFIG_PATHS

    def test_returns_empty_dict_when_all_paths_missing(self, monkeypatch: pytest.MonkeyPatch):
        mod = _mod()
        monkeypatch.delenv("AGENT_CONFIG", raising=False)

        with patch.object(mod.os.path, "isfile", return_value=False):
            assert mod._load_config() == {}


# ---------------------------------------------------------------------------
# main() — daemon configuration (env > TOML > hardcoded defaults)
# ---------------------------------------------------------------------------


class TestMainApiUrl:
    def test_hardcoded_default_when_no_env_or_config(self):
        daemon_cls, _, _ = _run_main()
        assert daemon_cls.call_args.kwargs["api_url"] == "https://infraq.app/api/v1/collectors"

    def test_env_var_overrides_default(self):
        daemon_cls, _, _ = _run_main(env={"AGENT_API_URL": "https://my.api/v2"})
        assert daemon_cls.call_args.kwargs["api_url"] == "https://my.api/v2"

    def test_toml_config_used_when_no_env(self):
        cfg: dict[str, object] = {"agent": {"api_url": "https://cfg.host/api"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["api_url"] == "https://cfg.host/api"

    def test_env_var_beats_toml_config(self):
        cfg: dict[str, object] = {"agent": {"api_url": "https://cfg.host/api"}}
        daemon_cls, _, _ = _run_main(
            env={"AGENT_API_URL": "https://env.host/api"},
            config=cfg,
        )
        assert daemon_cls.call_args.kwargs["api_url"] == "https://env.host/api"


class TestMainHostCode:
    def test_default_is_localhost(self):
        daemon_cls, _, _ = _run_main()
        assert daemon_cls.call_args.kwargs["host_code"] == "localhost"

    def test_env_var_override(self):
        daemon_cls, _, _ = _run_main(env={"AGENT_HOST_CODE": "lxc-prod-42"})
        assert daemon_cls.call_args.kwargs["host_code"] == "lxc-prod-42"

    def test_toml_config_used_when_no_env(self):
        cfg: dict[str, object] = {"agent": {"host_code": "cfg-host-01"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["host_code"] == "cfg-host-01"

    def test_env_var_beats_config(self):
        cfg: dict[str, object] = {"agent": {"host_code": "cfg-host-99"}}
        daemon_cls, _, _ = _run_main(
            env={"AGENT_HOST_CODE": "env-host-01"},
            config=cfg,
        )
        assert daemon_cls.call_args.kwargs["host_code"] == "env-host-01"


class TestMainLogLevel:
    def test_default_is_info(self):
        daemon_cls, _, _ = _run_main()
        assert daemon_cls.call_args.kwargs["log_level"] == "INFO"

    def test_env_var_override(self):
        daemon_cls, _, _ = _run_main(env={"AGENT_LOG_LEVEL": "DEBUG"})
        assert daemon_cls.call_args.kwargs["log_level"] == "DEBUG"

    def test_toml_config_used_when_no_env(self):
        cfg: dict[str, object] = {"agent": {"log_level": "WARNING"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["log_level"] == "WARNING"


class TestMainVerifySsl:
    def test_default_is_true(self):
        daemon_cls, _, _ = _run_main()
        assert daemon_cls.call_args.kwargs["verify_ssl"] is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "NO"])
    def test_falsy_string_values_disable_ssl(self, value: str):
        daemon_cls, _, _ = _run_main(env={"AGENT_VERIFY_SSL": value})
        assert daemon_cls.call_args.kwargs["verify_ssl"] is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "YES"])
    def test_truthy_string_values_keep_ssl_enabled(self, value: str):
        daemon_cls, _, _ = _run_main(env={"AGENT_VERIFY_SSL": value})
        assert daemon_cls.call_args.kwargs["verify_ssl"] is True

    def test_config_verify_ssl_false(self):
        cfg: dict[str, object] = {"agent": {"verify_ssl": "false"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["verify_ssl"] is False


class TestMainCaBundle:
    def test_default_is_none(self):
        daemon_cls, _, _ = _run_main()
        assert daemon_cls.call_args.kwargs["ca_bundle"] is None

    def test_env_var_set(self):
        daemon_cls, _, _ = _run_main(env={"AGENT_CA_BUNDLE": "/etc/ssl/ca.pem"})
        assert daemon_cls.call_args.kwargs["ca_bundle"] == "/etc/ssl/ca.pem"

    def test_empty_string_becomes_none(self):
        """Empty ca_bundle env var is falsy and must resolve to None."""
        daemon_cls, _, _ = _run_main(env={"AGENT_CA_BUNDLE": ""})
        assert daemon_cls.call_args.kwargs["ca_bundle"] is None

    def test_toml_config_path(self):
        cfg: dict[str, object] = {"agent": {"ca_bundle": "/cfg/ca.pem"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["ca_bundle"] == "/cfg/ca.pem"

    def test_env_beats_config(self):
        cfg: dict[str, object] = {"agent": {"ca_bundle": "/cfg/ca.pem"}}
        daemon_cls, _, _ = _run_main(
            env={"AGENT_CA_BUNDLE": "/env/ca.pem"},
            config=cfg,
        )
        assert daemon_cls.call_args.kwargs["ca_bundle"] == "/env/ca.pem"


# ---------------------------------------------------------------------------
# main() — non-HTTPS warning
# ---------------------------------------------------------------------------


class TestMainHttpsWarning:
    def test_non_https_url_prints_warning_to_stderr(self, capsys: pytest.CaptureFixture[str]):
        _run_main(env={"AGENT_API_URL": "http://insecure.host/api"})
        err = capsys.readouterr().err
        assert "WARNING" in err
        assert "http://insecure.host/api" in err
        assert "TLS" in err

    def test_https_url_no_warning(self, capsys: pytest.CaptureFixture[str]):
        _run_main(env={"AGENT_API_URL": "https://secure.host/api"})
        assert capsys.readouterr().err == ""

    def test_default_url_is_https_no_warning(self, capsys: pytest.CaptureFixture[str]):
        """The hardcoded default URL starts with https:// so no warning."""
        _run_main()
        assert capsys.readouterr().err == ""

    def test_warning_message_mentions_url(self, capsys: pytest.CaptureFixture[str]):
        _run_main(env={"AGENT_API_URL": "http://plain-http.example.com"})
        err = capsys.readouterr().err
        assert "plain-http.example.com" in err


# ---------------------------------------------------------------------------
# main() — event loop lifecycle
# ---------------------------------------------------------------------------


class TestMainEventLoop:
    def test_daemon_start_called_via_run_until_complete(self):
        _, daemon_instance, mock_loop = _run_main()
        mock_loop.run_until_complete.assert_called_once_with(daemon_instance.start())

    def test_loop_closed_after_normal_run(self):
        _, _, mock_loop = _run_main()
        mock_loop.close.assert_called_once()

    def test_keyboard_interrupt_calls_daemon_stop(self):
        mod = _mod()
        mock_loop = _make_loop()
        daemon_cls = MagicMock()
        daemon_instance = MagicMock()
        daemon_cls.return_value = daemon_instance
        mock_asyncio = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_signal = MagicMock()
        mock_signal.SIGTERM = _signal_mod.SIGTERM
        mock_signal.SIGINT = _signal_mod.SIGINT

        # First run_until_complete(daemon.start()) raises KeyboardInterrupt;
        # second call is run_until_complete(daemon.stop()) which succeeds.
        mock_loop.run_until_complete.side_effect = [KeyboardInterrupt, None]

        with (
            patch.object(mod, "_load_config", return_value={}),
            patch.object(mod, "AgentDaemon", daemon_cls),
            patch(f"{_MODULE}.asyncio", mock_asyncio),
            patch(f"{_MODULE}.signal", mock_signal),
            patch.dict("os.environ", {}, clear=True),
        ):
            mod.main()

        assert mock_loop.run_until_complete.call_count == 2
        mock_loop.run_until_complete.assert_called_with(daemon_instance.stop())

    def test_loop_closed_after_keyboard_interrupt(self):
        mod = _mod()
        mock_loop = _make_loop()
        mock_loop.run_until_complete.side_effect = [KeyboardInterrupt, None]
        daemon_cls = MagicMock()
        daemon_cls.return_value = MagicMock()
        mock_asyncio = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        mock_signal = MagicMock()
        mock_signal.SIGTERM = _signal_mod.SIGTERM
        mock_signal.SIGINT = _signal_mod.SIGINT

        with (
            patch.object(mod, "_load_config", return_value={}),
            patch.object(mod, "AgentDaemon", daemon_cls),
            patch(f"{_MODULE}.asyncio", mock_asyncio),
            patch(f"{_MODULE}.signal", mock_signal),
            patch.dict("os.environ", {}, clear=True),
        ):
            mod.main()

        mock_loop.close.assert_called_once()


# ---------------------------------------------------------------------------
# main() — signal handlers
# ---------------------------------------------------------------------------


class TestMainSignalHandlers:
    def _get_signal_mock(self) -> MagicMock:
        """Run main() and return the signal mock so caller can inspect calls."""
        mod = _mod()
        mock_loop = _make_loop()
        daemon_cls = MagicMock()
        daemon_cls.return_value = MagicMock()
        mock_asyncio = MagicMock()
        mock_asyncio.new_event_loop.return_value = mock_loop
        sig_mock = MagicMock()
        sig_mock.SIGTERM = _signal_mod.SIGTERM
        sig_mock.SIGINT = _signal_mod.SIGINT

        with (
            patch.object(mod, "_load_config", return_value={}),
            patch.object(mod, "AgentDaemon", daemon_cls),
            patch(f"{_MODULE}.asyncio", mock_asyncio),
            patch(f"{_MODULE}.signal", sig_mock),
            patch.dict("os.environ", {}, clear=True),
        ):
            mod.main()

        return sig_mock

    def test_sigterm_handler_registered(self):
        sig_mock = self._get_signal_mock()
        registered = [c.args[0] for c in sig_mock.signal.call_args_list]
        assert _signal_mod.SIGTERM in registered

    def test_sigint_handler_registered(self):
        sig_mock = self._get_signal_mock()
        registered = [c.args[0] for c in sig_mock.signal.call_args_list]
        assert _signal_mod.SIGINT in registered

    def test_both_handlers_use_same_callable(self):
        """SIGTERM and SIGINT should share the same ``_shutdown`` closure."""
        sig_mock = self._get_signal_mock()
        handlers = {c.args[0]: c.args[1] for c in sig_mock.signal.call_args_list}
        assert handlers[_signal_mod.SIGTERM] is handlers[_signal_mod.SIGINT]

    def test_exactly_two_signal_registrations(self):
        sig_mock = self._get_signal_mock()
        assert sig_mock.signal.call_count == 2


# ---------------------------------------------------------------------------
# main() — agent_conf parsing from TOML (dict coercion)
# ---------------------------------------------------------------------------


class TestMainAgentConfParsing:
    """Verify that non-string TOML values are coerced to strings correctly."""

    def test_integer_api_url_coerced_to_string(self):
        """Numeric values in [agent] table must be str()-coerced before use."""
        # Provide a numeric port as host_code (unusual but valid TOML)
        cfg: dict[str, object] = {"agent": {"host_code": 42}}
        daemon_cls, _, _ = _run_main(config=cfg)
        # str(42) == "42" — daemon should receive a string
        assert daemon_cls.call_args.kwargs["host_code"] == "42"

    def test_non_dict_agent_section_ignored(self):
        """If [agent] is not a TOML table, the section is skipped and defaults apply."""
        cfg: dict[str, object] = {"agent": "not-a-dict"}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["host_code"] == "localhost"

    def test_missing_agent_section_uses_all_defaults(self):
        cfg: dict[str, object] = {"other_section": {"key": "value"}}
        daemon_cls, _, _ = _run_main(config=cfg)
        assert daemon_cls.call_args.kwargs["api_url"] == "https://infraq.app/api/v1/collectors"
        assert daemon_cls.call_args.kwargs["host_code"] == "localhost"
        assert daemon_cls.call_args.kwargs["log_level"] == "INFO"
        assert daemon_cls.call_args.kwargs["verify_ssl"] is True
        assert daemon_cls.call_args.kwargs["ca_bundle"] is None
