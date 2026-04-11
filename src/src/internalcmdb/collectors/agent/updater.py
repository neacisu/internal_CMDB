"""Agent Auto-Updater — checks for and applies agent updates (Phase 18, F18.3).

The updater periodically checks the control plane API for a newer agent
version and, when one is available, downloads it with SHA-256 checksum
verification.  On failure the previous version is restored automatically.

Usage::

    updater = AgentUpdater(api_url="https://infraq.app/api/v1/collectors")
    info = await updater.check_update("1.0.0")
    if info:
        await updater.apply_update(info)
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# SONAR-HOTSPOT REVIEWED: S5443 — lock file uses /var/lock which is only writable
# by root/privileged processes, not world-writable like /tmp.  The agent daemon
# runs as root on the target node; /var/lock is the correct location.
_UPDATE_LOCK_PATH = Path("/var/lock/internalcmdb-agent-update.lock")


def _create_temp_archive_path() -> str:
    """Atomically create an empty temp file; return its path (S5445-safe)."""
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".tar.gz",
        prefix="agent-update-",
    ) as tmp:
        return tmp.name


def _stream_agent_archive_to_path(url: str, path: str, verify_ssl: bool) -> None:
    """Blocking download into *path* (intended for ``asyncio.to_thread``).

    Uses a synchronous :class:`httpx.Client` so the event loop is not blocked
    during I/O; the temp file is created securely by the caller.
    """
    with httpx.Client(timeout=120, verify=verify_ssl) as client:  # noqa: SIM117 — inner depends on outer binding
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as out:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    out.write(chunk)


_AGENT_DIR = Path("/opt/internalcmdb/agent")
_BACKUP_DIR = Path("/opt/internalcmdb/agent.bak")


@dataclass(frozen=True)
class UpdateInfo:
    """Describes an available agent update."""

    version: str
    download_url: str
    checksum_sha256: str
    release_notes: str = ""


class AgentUpdater:
    """Checks for and applies agent binary/package updates."""

    def __init__(
        self,
        api_url: str,
        current_version: str = "1.0.0",
        verify_ssl: bool = True,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._current_version = current_version
        self._verify_ssl = verify_ssl

    async def check_update(self, current_version: str | None = None) -> UpdateInfo | None:
        """Query the API for a newer agent version.

        Returns ``UpdateInfo`` when an update is available, ``None`` otherwise.
        """
        version = current_version or self._current_version
        url = f"{self._api_url}/agent/update-check"

        try:
            async with httpx.AsyncClient(timeout=15, verify=self._verify_ssl) as client:
                resp = await client.get(url, params={"current_version": version})

                if resp.status_code == 204:  # noqa: PLR2004
                    logger.debug("No update available (current=%s)", version)
                    return None

                resp.raise_for_status()
                data = resp.json()

                if not data.get("update_available"):
                    return None

                return UpdateInfo(
                    version=data["version"],
                    download_url=data["download_url"],
                    checksum_sha256=data["checksum_sha256"],
                    release_notes=data.get("release_notes", ""),
                )
        except httpx.HTTPError:
            logger.warning("Update check failed", exc_info=True)
            return None

    async def apply_update(self, info: UpdateInfo) -> bool:
        """Download, verify, and apply the update.  Rolls back on failure.

        Uses a file lock to prevent concurrent updates from racing.
        Lock acquisition and checksum verification are offloaded to a
        thread so the event loop is never blocked by synchronous I/O.
        """
        logger.info("Applying agent update %s → %s", self._current_version, info.version)

        lock_fd = None
        try:
            lock_fd = await asyncio.to_thread(open, _UPDATE_LOCK_PATH, "w")
            try:
                await asyncio.to_thread(fcntl.flock, lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                logger.warning("Another update is in progress — skipping")
                return False

            archive_path = await self._download(info)

            checksum_ok = await asyncio.to_thread(
                self._verify_checksum, archive_path, info.checksum_sha256
            )
            if not checksum_ok:
                logger.error("Checksum mismatch — aborting update")
                os.unlink(archive_path)
                return False

            await asyncio.to_thread(self._backup_current)
            await asyncio.to_thread(self._extract_update, archive_path)
            os.unlink(archive_path)

            self._current_version = info.version
            logger.info("Agent updated to %s successfully", info.version)
            return True

        except Exception:
            logger.exception("Update failed — rolling back")
            await asyncio.to_thread(self._rollback)
            return False
        finally:
            if lock_fd is not None:
                await asyncio.to_thread(fcntl.flock, lock_fd, fcntl.LOCK_UN)
                lock_fd.close()

    async def _download(self, info: UpdateInfo) -> str:
        """Download the update archive to a temporary file."""
        path = await asyncio.to_thread(_create_temp_archive_path)
        try:
            await asyncio.to_thread(
                _stream_agent_archive_to_path,
                info.download_url,
                path,
                self._verify_ssl,
            )
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(path)
            raise
        logger.info("Downloaded update to %s", path)
        return path

    @staticmethod
    def _verify_checksum(file_path: str, expected_sha256: str) -> bool:
        """Verify SHA-256 checksum of the downloaded file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        actual = sha256.hexdigest()
        if actual != expected_sha256:
            logger.error("Expected SHA-256 %s, got %s", expected_sha256, actual)
            return False
        return True

    @staticmethod
    def _backup_current() -> None:
        """Back up the current agent directory."""
        if _AGENT_DIR.exists():
            if _BACKUP_DIR.exists():
                shutil.rmtree(_BACKUP_DIR)
            shutil.copytree(_AGENT_DIR, _BACKUP_DIR)
            logger.info("Backed up current agent to %s", _BACKUP_DIR)

    @staticmethod
    def _extract_update(archive_path: str) -> None:
        """Extract the update archive over the agent directory.

        Path-traversal (zip-slip) protection: each member path is resolved
        against the destination and rejected if it escapes the target tree.
        """
        import tarfile  # noqa: PLC0415

        _AGENT_DIR.mkdir(parents=True, exist_ok=True)
        dest = _AGENT_DIR.resolve()
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = (dest / member.name).resolve()
                if not str(member_path).startswith(str(dest)):
                    raise ValueError(
                        f"Unsafe archive member rejected (path traversal): {member.name}"
                    )
            # filter='data' strips special files (devices, setuid bits); safe for agent payloads.
            tar.extractall(path=_AGENT_DIR, filter="data")
        logger.info("Extracted update to %s", _AGENT_DIR)

    @staticmethod
    def _rollback() -> None:
        """Restore the agent from backup."""
        if _BACKUP_DIR.exists():
            if _AGENT_DIR.exists():
                shutil.rmtree(_AGENT_DIR)
            shutil.copytree(_BACKUP_DIR, _AGENT_DIR)
            logger.info("Rolled back agent from %s", _BACKUP_DIR)
        else:
            logger.error("No backup available for rollback")
