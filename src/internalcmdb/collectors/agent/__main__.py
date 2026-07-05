"""Agent entrypoint — ``python -m internalcmdb.collectors.agent``."""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Any, cast

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from .daemon import AgentDaemon

DEFAULT_CONFIG_PATHS = [
    "/etc/internalcmdb/agent.toml",
    os.path.expanduser("~/.config/internalcmdb/agent.toml"),
    "agent.toml",
]


def _load_config() -> dict[str, object]:
    """Load agent configuration from TOML file."""
    config_path = os.environ.get("AGENT_CONFIG")
    paths = [config_path] if config_path else DEFAULT_CONFIG_PATHS

    for path in paths:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                return tomllib.load(f)

    return {}


def main() -> None:
    """Start the agent daemon."""
    config = _load_config()
    agent_conf: dict[str, str] = {}
    raw = config.get("agent", {})
    if isinstance(raw, dict):
        raw_typed: dict[str, Any] = cast(dict[str, Any], raw)
        agent_conf = {str(k): str(v) for k, v in raw_typed.items()}

    api_url = os.environ.get(
        "AGENT_API_URL",
        str(agent_conf.get("api_url", "https://infraq.app/api/v1/collectors")),
    )
    host_code = os.environ.get(
        "AGENT_HOST_CODE",
        str(agent_conf.get("host_code", "localhost")),
    )
    log_level = os.environ.get(
        "AGENT_LOG_LEVEL",
        str(agent_conf.get("log_level", "INFO")),
    )
    verify_ssl_raw = os.environ.get(
        "AGENT_VERIFY_SSL",
        str(agent_conf.get("verify_ssl", "true")),
    )
    verify_ssl = verify_ssl_raw.lower() not in ("false", "0", "no")

    ca_bundle = (
        os.environ.get(
            "AGENT_CA_BUNDLE",
            str(agent_conf.get("ca_bundle", "")),
        )
        or None
    )
    enrollment_token = os.environ.get(
        "INTERNALCMDB_BOOTSTRAP_TOKEN",
        str(agent_conf.get("enrollment_token", "")),
    )
    bootstrap_token_path = os.environ.get(
        "AGENT_BOOTSTRAP_TOKEN_PATH",
        str(agent_conf.get("bootstrap_token_path", "/etc/internalcmdb/bootstrap.token")),
    )
    credentials_path = os.environ.get(
        "AGENT_CREDENTIALS_PATH",
        str(agent_conf.get("credentials_path", "/var/log/internalcmdb/agent-credentials.json")),
    )
    redis_url = os.environ.get(
        "AGENT_REDIS_URL",
        str(agent_conf.get("redis_url", "")),
    )

    if not api_url.startswith("https://"):
        import sys  # noqa: PLC0415

        print(
            f"WARNING: api_url '{api_url}' is not HTTPS — TLS is strongly recommended",
            file=sys.stderr,
        )

    daemon = AgentDaemon(
        api_url=str(api_url),
        host_code=str(host_code),
        log_level=str(log_level),
        verify_ssl=verify_ssl,
        ca_bundle=ca_bundle,
        enrollment_token=str(enrollment_token),
        bootstrap_token_path=str(bootstrap_token_path),
        credentials_path=str(credentials_path),
        redis_url=str(redis_url),
    )

    _pending_tasks: set[asyncio.Task[Any]] = set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(_signum: int, _frame: object) -> None:
        task = loop.create_task(daemon.stop())
        _pending_tasks.add(task)
        task.add_done_callback(_pending_tasks.discard)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(daemon.start())
    except KeyboardInterrupt:
        loop.run_until_complete(daemon.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
