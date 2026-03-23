"""Agent entrypoint — ``python -m internalcmdb.collectors.agent``."""

from __future__ import annotations

import asyncio
import os
import signal

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
        agent_conf = {str(k): str(v) for k, v in raw.items()}

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

    ca_bundle = os.environ.get(
        "AGENT_CA_BUNDLE",
        str(agent_conf.get("ca_bundle", "")),
    ) or None

    if not api_url.startswith("https://"):
        import sys  # noqa: PLC0415

        print(  # noqa: T201
            f"WARNING: api_url '{api_url}' is not HTTPS — TLS is strongly recommended",
            file=sys.stderr,
        )

    daemon = AgentDaemon(
        api_url=str(api_url),
        host_code=str(host_code),
        log_level=str(log_level),
        verify_ssl=verify_ssl,
        ca_bundle=ca_bundle,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(_signum: int, _frame: object) -> None:
        _task = loop.create_task(daemon.stop())  # noqa: RUF006

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
