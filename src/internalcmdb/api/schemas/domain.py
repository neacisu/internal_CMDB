"""Pydantic v2 schemas for discovery, governance, retrieval, and agent models."""

from __future__ import annotations

import uuid
from typing import Any

from .common import DatetimeStr, OptDatetimeStr, OrmBase

# --- Discovery ---


class DiscoverySourceOut(OrmBase):
    discovery_source_id: uuid.UUID
    source_code: str
    name: str
    tool_path: str | None = None
    command_template: str | None = None
    is_read_only: bool
    description: str | None = None
    created_at: DatetimeStr


class CollectionRunOut(OrmBase):
    collection_run_id: uuid.UUID
    discovery_source_id: uuid.UUID
    run_code: str
    target_scope_jsonb: dict[str, Any] | None = None
    started_at: DatetimeStr
    finished_at: OptDatetimeStr = None
    executor_identity: str
    raw_output_path: str | None = None
    summary_jsonb: dict[str, Any] | None = None


class ObservedFactOut(OrmBase):
    observed_fact_id: uuid.UUID
    collection_run_id: uuid.UUID
    entity_id: uuid.UUID
    fact_namespace: str
    fact_key: str
    fact_value_jsonb: dict[str, Any] | None = None
    confidence_score: float | None = None
    observed_at: DatetimeStr


class EvidenceArtifactOut(OrmBase):
    evidence_artifact_id: uuid.UUID
    collection_run_id: uuid.UUID
    artifact_path: str | None = None
    artifact_hash: str | None = None
    mime_type: str | None = None
    content_excerpt_text: str | None = None
    metadata_jsonb: dict[str, Any] | None = None
    created_at: DatetimeStr


# --- Governance ---


class PolicyRecordOut(OrmBase):
    policy_record_id: uuid.UUID
    policy_code: str
    name: str
    scope_text: str | None = None
    is_active: bool
    created_at: DatetimeStr
    updated_at: DatetimeStr


class ApprovalRecordOut(OrmBase):
    approval_record_id: uuid.UUID
    approval_code: str
    entity_id: uuid.UUID
    requested_by: str
    approved_by: str | None = None
    status_text: str
    expires_at: OptDatetimeStr = None
    created_at: DatetimeStr
    updated_at: DatetimeStr


class ChangeLogOut(OrmBase):
    change_log_id: uuid.UUID
    change_code: str
    entity_id: uuid.UUID
    change_source_text: str
    change_summary_text: str
    changed_by: str
    changed_at: DatetimeStr
    created_at: DatetimeStr


# --- Retrieval ---


class DocumentChunkOut(OrmBase):
    document_chunk_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    chunk_hash: str
    content_text: str
    token_count: int | None = None
    section_path_text: str | None = None
    metadata_jsonb: dict[str, Any] | None = None
    created_at: DatetimeStr


class EvidencePackOut(OrmBase):
    evidence_pack_id: uuid.UUID
    pack_code: str
    task_type_code: str
    request_scope_jsonb: dict[str, Any] | None = None
    selection_rationale_text: str | None = None
    token_budget: int | None = None
    created_by: str
    created_at: DatetimeStr


# --- Agent Control ---


class PromptTemplateOut(OrmBase):
    prompt_template_registry_id: uuid.UUID
    template_code: str
    task_type_code: str
    template_version: str
    is_active: bool
    created_at: DatetimeStr
    updated_at: DatetimeStr


class AgentRunOut(OrmBase):
    agent_run_id: uuid.UUID
    run_code: str
    agent_identity: str
    task_type_code: str
    status_text: str
    started_at: DatetimeStr
    finished_at: OptDatetimeStr = None
    created_at: DatetimeStr


class ActionRequestOut(OrmBase):
    action_request_id: uuid.UUID
    request_code: str
    action_class_text: str
    target_scope_jsonb: dict[str, Any] | None = None
    requested_change_jsonb: dict[str, Any] | None = None
    status_text: str
    executed_at: OptDatetimeStr = None
    created_at: DatetimeStr
