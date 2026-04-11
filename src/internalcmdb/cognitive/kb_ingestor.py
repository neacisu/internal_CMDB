"""Knowledge Base Ingestor — populate retrieval.chunk_embedding from live CMDB data and docs.

Sources ingested:
  1. registry.host          — one text chunk per host (code, status, env, tags)
  2. shared_infrastructure.shared_service — one chunk per service
  3. cognitive.insight (active) — one chunk per active insight
  4. docs/ Markdown files   — chunked via KnowledgeBase.embed_document
  5. subprojects/ Markdown / JSON reports — chunked via KnowledgeBase.embed_document

Deduplication is handled by KnowledgeBase.embed_document which checks
``retrieval.document_chunk.chunk_hash`` before inserting.

Usage (manual trigger)::

    from sqlalchemy.ext.asyncio import AsyncSession
    from internalcmdb.llm.client import LLMClient
    from internalcmdb.cognitive.kb_ingestor import KnowledgeBaseIngestor

    async with LLMClient.from_settings() as llm:
        ingestor = KnowledgeBaseIngestor()
        summary = await ingestor.ingest_all(session, llm)
        print(summary)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from internalcmdb.cognitive.knowledge_base import KnowledgeBase
from internalcmdb.llm.client import LLMClient

logger = logging.getLogger(__name__)

# Minimum scalar value length that adds search value (< this length → skip)
_MIN_SEARCH_VALUE_LEN = 3
# ---------------------------------------------------------------------------
# JSON-flattening helper (module-level to keep _json_to_text complexity low)
# ---------------------------------------------------------------------------


def _walk_json_value(obj: Any, prefix: str, lines: list[str]) -> None:
    """Recursively flatten *obj* into *lines* with dot-path *prefix*.

    Dicts are traversed key-by-key, lists are capped at 50 items.
    Scalar values that look purely numeric or are very short are skipped
    because they add no search value.
    """
    if isinstance(obj, dict):
        obj_dict = cast(dict[str, Any], obj)
        for k, v in obj_dict.items():
            next_prefix = f"{prefix}{k}: " if not prefix else f"{prefix}.{k}: "
            _walk_json_value(v, next_prefix, lines)
    elif isinstance(obj, list):
        obj_list = cast(list[Any], obj)
        for i, item in enumerate(obj_list[:50]):  # cap list expansion
            _walk_json_value(item, f"{prefix}[{i}] ", lines)
    else:
        val = str(obj)
        # Skip numeric-only or very short values that don't add search value
        if len(val) > _MIN_SEARCH_VALUE_LEN and not val.lstrip("-").replace(".", "").isdigit():
            lines.append(f"{prefix}{val}")


_REPO_ROOT = Path(__file__).resolve().parents[3]  # …/internalcmdb/
_DOCS_DIR = _REPO_ROOT / "docs"
_SUBPROJECTS_DIR = _REPO_ROOT / "subprojects"

# Maximum bytes to read from a single file (prevent huge files clogging the embed queue)
_MAX_FILE_BYTES = 512 * 1024  # 512 KB


# ---------------------------------------------------------------------------
# Host-chunk text-building helpers (extracted to keep _ingest_hosts ≤ 15 CC)
# ---------------------------------------------------------------------------


def _build_tags_str(raw_tags: Any) -> str:
    """Convert the raw ``tags`` JSON value of a host row to a display string."""
    if not raw_tags:
        return ""
    if isinstance(raw_tags, list):
        return ", ".join(str(t) for t in cast(list[Any], raw_tags))
    return str(raw_tags)


def _build_metrics_parts(row: Mapping[str, Any]) -> list[str]:
    """Return ordered metric tokens for a host content chunk.

    Priority order:
    1. CPU usage percentage (from system_vitals snapshot)
    2. Memory: mem_usage_pct if available, else ram_used/total GB, else ram_total only
    3. CPU core count + model (from host_hardware_snapshot)
    """
    parts: list[str] = []
    if row["cpu_usage_pct"] is not None:
        parts.append(f"cpu_usage={row['cpu_usage_pct']}%")
    if row["mem_usage_pct"] is not None:
        parts.append(f"memory_usage={row['mem_usage_pct']}%")
    elif row["ram_used_gb"] is not None and row["ram_total_gb"] is not None:
        parts.append(f"ram={row['ram_used_gb']}GB/{row['ram_total_gb']}GB")
    elif row["ram_total_gb"] is not None:
        parts.append(f"ram_total={row['ram_total_gb']}GB")
    if row["cpu_core_count"] is not None:
        cpu_label = f"cpu_cores={row['cpu_core_count']}"
        if row["cpu_model"]:
            cpu_label += f" ({row['cpu_model']})"
        parts.append(cpu_label)
    return parts


def _build_host_content(row: Mapping[str, Any]) -> str:
    """Compose the full searchable text chunk for a single host row."""
    tags_str = _build_tags_str(row["tags"])
    metrics_parts = _build_metrics_parts(row)
    return (
        f"Host {row['host_code']}: "
        f"status={row['status'] or 'unknown'}, "
        f"environment={row['environment'] or 'unknown'}"
        + (f", tags={tags_str}" if tags_str else "")
        + (f", {', '.join(metrics_parts)}" if metrics_parts else "")
    )


class KnowledgeBaseIngestor:
    """Ingest all knowledge sources into the pgvector knowledge base."""

    async def ingest_all(
        self,
        session: AsyncSession,
        llm: LLMClient,
    ) -> dict[str, int]:
        """Run all ingestion sources and return chunk counts per source.

        Returns a dict like::

            {"hosts": 14, "services": 8, "insights": 23, "docs": 47,
             "subprojects": 12, "total": 104}
        """
        kb = KnowledgeBase(session, llm)

        counts: dict[str, int] = {
            "hosts": 0,
            "services": 0,
            "insights": 0,
            "docs": 0,
            "subprojects": 0,
        }

        counts["hosts"] = await self._safe_ingest("hosts", self._ingest_hosts, session, kb)
        counts["services"] = await self._safe_ingest("services", self._ingest_services, session, kb)
        counts["insights"] = await self._safe_ingest("insights", self._ingest_insights, session, kb)
        counts["docs"] = await self._safe_ingest_dir("docs", kb, _DOCS_DIR, "docs")
        counts["subprojects"] = await self._safe_ingest_dir(
            "subprojects", kb, _SUBPROJECTS_DIR, "subprojects"
        )

        counts["total"] = sum(v for k, v in counts.items() if k != "total")
        logger.info(
            "KB ingest complete: %d hosts, %d services, %d insights, "
            "%d docs, %d subproject chunks (total %d)",
            counts["hosts"],
            counts["services"],
            counts["insights"],
            counts["docs"],
            counts["subprojects"],
            counts["total"],
        )
        return counts

    # ------------------------------------------------------------------
    # Source isolation helpers — each source runs in a savepoint so a
    # failure in one source never poisons the outer transaction.
    # ------------------------------------------------------------------

    async def _safe_ingest(
        self,
        name: str,
        fn: Any,
        session: AsyncSession,
        kb: KnowledgeBase,
    ) -> int:
        try:
            return await fn(session, kb)
        except Exception:
            logger.warning("KB ingest source '%s' failed — skipping.", name, exc_info=True)
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await session.rollback()
            return 0

    async def _safe_ingest_dir(
        self,
        name: str,
        kb: KnowledgeBase,
        directory: Path,
        source_tag: str,
    ) -> int:
        try:
            return await self._ingest_directory(kb, directory, source_tag=source_tag)
        except Exception:
            logger.warning("KB ingest source '%s' failed — skipping.", name, exc_info=True)
            import contextlib  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await kb._session.rollback()
            return 0

    # ------------------------------------------------------------------
    # Source 1 — CMDB hosts
    # ------------------------------------------------------------------

    async def _ingest_hosts(self, session: AsyncSession, kb: KnowledgeBase) -> int:
        """Emit one text chunk per host from registry.host, enriched with live metrics."""
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT h.host_id::text,
                           h.host_code,
                           t_lc.display_name  AS status,
                           t_env.display_name AS environment,
                           h.metadata_jsonb -> 'tags' AS tags,
                           -- CPU usage from latest system_vitals snapshot (lifetime cumulative)
                           ROUND(CAST(
                               100.0 * (
                                   (sv.payload_jsonb->'cpu_times'->>'user')::float
                                   + (sv.payload_jsonb->'cpu_times'->>'system')::float
                               ) / NULLIF(
                                   (sv.payload_jsonb->'cpu_times'->>'user')::float
                                   + (sv.payload_jsonb->'cpu_times'->>'system')::float
                                   + (sv.payload_jsonb->'cpu_times'->>'idle')::float, 0
                               ) AS numeric
                           ), 1) AS cpu_usage_pct,
                           -- Memory from host_hardware_snapshot
                           ROUND(CAST(hhs.ram_used_bytes / 1073741824.0 AS numeric), 1)
                               AS ram_used_gb,
                           ROUND(CAST(hhs.ram_total_bytes / 1073741824.0 AS numeric), 1)
                               AS ram_total_gb,
                           ROUND(CAST(
                               100.0 * hhs.ram_used_bytes / NULLIF(hhs.ram_total_bytes, 0)
                               AS numeric
                           ), 1) AS mem_usage_pct,
                           hhs.cpu_core_count,
                           hhs.cpu_model
                    FROM registry.host h
                    LEFT JOIN taxonomy.taxonomy_term t_lc
                           ON t_lc.taxonomy_term_id = h.lifecycle_term_id
                    LEFT JOIN taxonomy.taxonomy_term t_env
                           ON t_env.taxonomy_term_id = h.environment_term_id
                    -- Latest system_vitals snapshot per host (via collector_agent)
                    LEFT JOIN LATERAL (
                        SELECT cs.payload_jsonb
                        FROM discovery.collector_snapshot cs
                        JOIN discovery.collector_agent ca ON ca.agent_id = cs.agent_id
                        WHERE ca.host_code = h.host_code
                          AND cs.snapshot_kind = 'system_vitals'
                        ORDER BY cs.collected_at DESC
                        LIMIT 1
                    ) sv ON true
                    -- Latest hardware snapshot for RAM + CPU info
                    LEFT JOIN LATERAL (
                        SELECT ram_used_bytes, ram_total_bytes, cpu_core_count, cpu_model
                        FROM registry.host_hardware_snapshot
                        WHERE host_id = h.host_id
                        ORDER BY observed_at DESC
                        LIMIT 1
                    ) hhs ON true
                    ORDER BY h.host_code
                """)
                )
            )
            .mappings()
            .all()
        )

        chunks_added = 0
        for row in rows:
            content = _build_host_content(cast(Mapping[str, Any], row))
            ids = await kb.embed_document(
                content,
                {
                    "source": "cmdb_host",
                    "host_id": row["host_id"],
                    "host_code": row["host_code"],
                },
            )
            chunks_added += len(ids)

        return chunks_added

    # ------------------------------------------------------------------
    # Source 2 — Services
    # ------------------------------------------------------------------

    async def _ingest_services(self, session: AsyncSession, kb: KnowledgeBase) -> int:
        """Emit one text chunk per shared service from registry.shared_service."""
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT shared_service_id::text, service_code, name, description
                    FROM registry.shared_service
                    WHERE is_active = true
                    ORDER BY service_code
                """)
                )
            )
            .mappings()
            .all()
        )

        chunks_added = 0
        for row in rows:
            desc = row["description"] or ""
            content = f"Service {row['name']} (code={row['service_code']}): {desc}".strip().rstrip(
                ":"
            )
            ids = await kb.embed_document(
                content,
                {
                    "source": "cmdb_service",
                    "service_id": row["shared_service_id"],
                    "service_code": row["service_code"],
                },
            )
            chunks_added += len(ids)

        return chunks_added

    # ------------------------------------------------------------------
    # Source 3 — Active cognitive insights
    # ------------------------------------------------------------------

    async def _ingest_insights(self, session: AsyncSession, kb: KnowledgeBase) -> int:
        """Embed active cognitive insights so the agent can search them via RAG."""
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT insight_id::text, severity, category,
                           title, explanation, entity_type
                    FROM cognitive.insight
                    WHERE status = 'active'
                    ORDER BY created_at DESC
                    LIMIT 500
                """)
                )
            )
            .mappings()
            .all()
        )

        chunks_added = 0
        for row in rows:
            explanation = row["explanation"] or ""
            content = (
                f"[{row['severity'].upper()}] {row['title']} "
                f"(category={row['category']}, entity={row['entity_type']})"
                + (f": {explanation}" if explanation else "")
            )
            ids = await kb.embed_document(
                content,
                {
                    "source": "cognitive_insight",
                    "insight_id": row["insight_id"],
                    "severity": row["severity"],
                    "category": row["category"],
                },
            )
            chunks_added += len(ids)

        return chunks_added

    # ------------------------------------------------------------------
    # Source 4+5 — File system directories (docs/, subprojects/)
    # ------------------------------------------------------------------

    async def _ingest_directory(
        self,
        kb: KnowledgeBase,
        directory: Path,
        *,
        source_tag: str,
    ) -> int:
        """Recursively embed Markdown and JSON text files from *directory*."""
        if not directory.is_dir():
            logger.debug("KB ingest: directory %s not found — skipping.", directory)
            return 0

        chunks_added = 0
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in (".md", ".json", ".txt"):
                continue

            try:
                content = self._read_file_safe(path)
            except Exception:
                logger.debug("KB ingest: failed to read %s — skipping.", path, exc_info=True)
                continue

            if not content.strip():
                continue

            # For JSON files keep only text-like values to avoid embedding raw numbers
            if path.suffix.lower() == ".json":
                content = self._json_to_text(content)
                if not content.strip():
                    continue

            rel_path = str(path.relative_to(_REPO_ROOT))
            ids = await kb.embed_document(
                content,
                {"source": source_tag, "file": rel_path},
            )
            chunks_added += len(ids)

        return chunks_added

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file_safe(path: Path) -> str:
        """Read up to _MAX_FILE_BYTES from a file, decoding as UTF-8."""
        with open(path, "rb") as fh:
            raw = fh.read(_MAX_FILE_BYTES)
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _json_to_text(raw: str) -> str:
        """Flatten a JSON document to human-readable key: value lines."""
        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError:
            return raw  # not valid JSON — return as-is

        lines: list[str] = []
        _walk_json_value(data, "", lines)
        return "\n".join(lines)
