"""wave1_initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-08 14:48:07.138172

Creates all Wave-1 schemas and tables for internalCMDB.

Schemas created (in dependency order):
  taxonomy, docs, discovery, governance, registry, retrieval, agent_control

NOTE: retrieval.chunk_embedding.embedding_vector is created as TEXT here.
      After enabling the pgvector extension on the server, run the companion
      migration 0002_enable_pgvector to ALTER it to vector(1536).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCHEMAS = (
    "taxonomy",
    "docs",
    "discovery",
    "governance",
    "registry",
    "retrieval",
    "agent_control",
)


def upgrade() -> None:
    # ── Create schemas ────────────────────────────────────────────────────────
    for schema in _SCHEMAS:
        op.execute(sa.text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

    # ── taxonomy.taxonomy_domain ──────────────────────────────────────────────
    op.create_table(
        "taxonomy_domain",
        sa.Column(
            "taxonomy_domain_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("domain_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("domain_code", name="uq_taxonomy_domain_code"),
        schema="taxonomy",
    )

    # ── taxonomy.taxonomy_term ────────────────────────────────────────────────
    op.create_table(
        "taxonomy_term",
        sa.Column(
            "taxonomy_term_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "taxonomy_domain_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_domain.taxonomy_domain_id"),
            nullable=False,
        ),
        sa.Column("term_code", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("parent_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_term_id"],
            ["taxonomy.taxonomy_term.taxonomy_term_id"],
            name="fk_taxonomy_term_parent",
        ),
        sa.UniqueConstraint(
            "taxonomy_domain_id",
            "term_code",
            name="uq_term_code_per_domain",
        ),
        schema="taxonomy",
    )

    # ── docs.document ─────────────────────────────────────────────────────────
    op.create_table(
        "document",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("document_path", sa.Text(), unique=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "status_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("owner_code", sa.Text()),
        sa.Column("source_repo_url", sa.Text()),
        sa.Column("source_branch", sa.Text()),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="docs",
    )

    # ── docs.document_version ─────────────────────────────────────────────────
    op.create_table(
        "document_version",
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("docs.document.document_id"),
            nullable=False,
        ),
        sa.Column("git_commit_sha", sa.Text()),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("frontmatter_jsonb", postgresql.JSONB()),
        sa.Column("body_excerpt_text", sa.Text()),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="docs",
    )

    # Add deferred FK from docs.document.current_version_id → docs.document_version
    op.create_foreign_key(
        "fk_document_current_version",
        "document",
        "document_version",
        ["current_version_id"],
        ["document_version_id"],
        source_schema="docs",
        referent_schema="docs",
    )

    # ── docs.document_entity_binding ─────────────────────────────────────────
    op.create_table(
        "document_entity_binding",
        sa.Column(
            "document_entity_binding_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("docs.document_version.document_version_id"),
            nullable=False,
        ),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("binding_role_text", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="docs",
    )

    # ── discovery.discovery_source ────────────────────────────────────────────
    op.create_table(
        "discovery_source",
        sa.Column(
            "discovery_source_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("source_code", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tool_path", sa.Text()),
        sa.Column("command_template", sa.Text()),
        sa.Column(
            "is_read_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("description", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="discovery",
    )

    # ── discovery.collection_run ──────────────────────────────────────────────
    op.create_table(
        "collection_run",
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "discovery_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.discovery_source.discovery_source_id"),
            nullable=False,
        ),
        sa.Column("run_code", sa.Text(), unique=True, nullable=False),
        sa.Column("target_scope_jsonb", postgresql.JSONB()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "status_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("executor_identity", sa.Text(), nullable=False),
        sa.Column("raw_output_path", sa.Text()),
        sa.Column("summary_jsonb", postgresql.JSONB()),
        schema="discovery",
    )

    # ── discovery.observed_fact ───────────────────────────────────────────────
    op.create_table(
        "observed_fact",
        sa.Column(
            "observed_fact_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fact_namespace", sa.Text(), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value_jsonb", postgresql.JSONB()),
        sa.Column(
            "observation_status_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="discovery",
    )

    # ── discovery.evidence_artifact ───────────────────────────────────────────
    op.create_table(
        "evidence_artifact",
        sa.Column(
            "evidence_artifact_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column(
            "evidence_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("artifact_path", sa.Text()),
        sa.Column("artifact_hash", sa.Text()),
        sa.Column("mime_type", sa.Text()),
        sa.Column("content_excerpt_text", sa.Text()),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="discovery",
    )

    # ── discovery.reconciliation_result ──────────────────────────────────────
    op.create_table(
        "reconciliation_result",
        sa.Column(
            "reconciliation_result_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_document_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column(
            "result_status_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("drift_category_text", sa.Text()),
        sa.Column("canonical_value_jsonb", postgresql.JSONB()),
        sa.Column("observed_value_jsonb", postgresql.JSONB()),
        sa.Column("diff_jsonb", postgresql.JSONB()),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["canonical_document_version_id"],
            ["docs.document_version.document_version_id"],
            name="fk_reconciliation_doc_version",
        ),
        schema="discovery",
    )

    # ── governance.policy_record ──────────────────────────────────────────────
    op.create_table(
        "policy_record",
        sa.Column(
            "policy_record_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("policy_code", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope_text", sa.Text()),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["docs.document_version.document_version_id"],
            name="fk_policy_record_doc_version",
        ),
        schema="governance",
    )

    # ── governance.approval_record ────────────────────────────────────────────
    op.create_table(
        "approval_record",
        sa.Column(
            "approval_record_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("approval_code", sa.Text(), unique=True, nullable=False),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_scope_jsonb", postgresql.JSONB()),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text()),
        sa.Column(
            "status_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="governance",
    )

    # ── registry.cluster ──────────────────────────────────────────────────────
    op.create_table(
        "cluster",
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("cluster_code", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "environment_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text()),
        sa.Column("canonical_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="registry",
    )

    # ── registry.host ─────────────────────────────────────────────────────────
    op.create_table(
        "host",
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.cluster.cluster_id"),
            nullable=True,
        ),
        sa.Column("host_code", sa.Text(), unique=True, nullable=False),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("ssh_alias", sa.Text()),
        sa.Column("fqdn", sa.Text()),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("primary_host_role_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "environment_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("os_family_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("os_version_text", sa.Text()),
        sa.Column("kernel_version_text", sa.Text()),
        sa.Column("architecture_text", sa.Text()),
        sa.Column(
            "is_gpu_capable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "is_docker_host",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "is_hypervisor",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("primary_public_ipv4", postgresql.INET()),
        sa.Column("primary_private_ipv4", postgresql.INET()),
        sa.Column("observed_hostname", sa.Text()),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["primary_host_role_term_id"],
            ["taxonomy.taxonomy_term.taxonomy_term_id"],
            name="fk_host_primary_role_term",
        ),
        sa.ForeignKeyConstraint(
            ["os_family_term_id"],
            ["taxonomy.taxonomy_term.taxonomy_term_id"],
            name="fk_host_os_family_term",
        ),
        schema="registry",
    )

    # ── registry.host_role_assignment ─────────────────────────────────────────
    op.create_table(
        "host_role_assignment",
        sa.Column(
            "host_role_assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column(
            "host_role_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("assignment_source_text", sa.Text()),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_host_role_assignment_run",
        ),
        schema="registry",
    )

    # ── registry.cluster_membership ───────────────────────────────────────────
    op.create_table(
        "cluster_membership",
        sa.Column(
            "cluster_membership_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.cluster.cluster_id"),
            nullable=False,
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column(
            "membership_role_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("member_node_name_text", sa.Text()),
        sa.Column("member_node_id_text", sa.Text()),
        sa.Column("membership_source_text", sa.Text()),
        sa.Column("is_quorate_member", sa.Boolean()),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_cluster_membership_run",
        ),
        schema="registry",
    )

    # ── registry.host_hardware_snapshot ──────────────────────────────────────
    op.create_table(
        "host_hardware_snapshot",
        sa.Column(
            "host_hardware_snapshot_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column("cpu_model", sa.Text()),
        sa.Column("cpu_socket_count", sa.Integer()),
        sa.Column("cpu_core_count", sa.Integer()),
        sa.Column("ram_total_bytes", sa.BigInteger()),
        sa.Column("ram_used_bytes", sa.BigInteger()),
        sa.Column("ram_free_bytes", sa.BigInteger()),
        sa.Column("swap_total_bytes", sa.BigInteger()),
        sa.Column("swap_used_bytes", sa.BigInteger()),
        sa.Column("gpu_count", sa.Integer()),
        sa.Column("hardware_jsonb", postgresql.JSONB()),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="registry",
    )

    # ── registry.gpu_device ───────────────────────────────────────────────────
    op.create_table(
        "gpu_device",
        sa.Column(
            "gpu_device_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column("gpu_index", sa.Integer(), nullable=False),
        sa.Column("vendor_name", sa.Text()),
        sa.Column("model_name", sa.Text()),
        sa.Column("uuid_text", sa.Text()),
        sa.Column("driver_version_text", sa.Text()),
        sa.Column("memory_total_mb", sa.Integer()),
        sa.Column("memory_used_mb", sa.Integer()),
        sa.Column("memory_free_mb", sa.Integer()),
        sa.Column("utilization_gpu_pct", sa.Numeric(5, 2)),
        sa.Column("utilization_memory_pct", sa.Numeric(5, 2)),
        sa.Column("temperature_celsius", sa.Numeric(5, 2)),
        sa.Column("power_draw_watts", sa.Numeric(8, 2)),
        sa.Column("power_limit_watts", sa.Numeric(8, 2)),
        sa.Column("fan_pct", sa.Numeric(5, 2)),
        sa.Column("compute_capability", sa.Text()),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="registry",
    )

    # ── registry.network_segment ──────────────────────────────────────────────
    op.create_table(
        "network_segment",
        sa.Column(
            "network_segment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("segment_code", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "segment_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "environment_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("cidr", postgresql.CIDR()),
        sa.Column("vlan_id_text", sa.Text()),
        sa.Column("mtu", sa.Integer()),
        sa.Column("description", sa.Text()),
        sa.Column("source_of_truth", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="registry",
    )

    # ── registry.network_interface ────────────────────────────────────────────
    op.create_table(
        "network_interface",
        sa.Column(
            "network_interface_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column("network_segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("interface_name", sa.Text(), nullable=False),
        sa.Column("parent_interface_name", sa.Text()),
        sa.Column("interface_kind_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state_text", sa.Text()),
        sa.Column("mac_address", postgresql.MACADDR()),
        sa.Column("mtu", sa.Integer()),
        sa.Column(
            "is_virtual",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["network_segment_id"],
            ["registry.network_segment.network_segment_id"],
            name="fk_network_interface_segment",
        ),
        sa.ForeignKeyConstraint(
            ["interface_kind_term_id"],
            ["taxonomy.taxonomy_term.taxonomy_term_id"],
            name="fk_network_interface_kind_term",
        ),
        schema="registry",
    )

    # ── registry.ip_address_assignment ───────────────────────────────────────
    op.create_table(
        "ip_address_assignment",
        sa.Column(
            "ip_address_assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "network_interface_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.network_interface.network_interface_id"),
            nullable=False,
        ),
        sa.Column("network_segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("address", postgresql.INET(), nullable=False),
        sa.Column("prefix_length", sa.Integer()),
        sa.Column(
            "address_scope_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["network_segment_id"],
            ["registry.network_segment.network_segment_id"],
            name="fk_ip_assignment_segment",
        ),
        schema="registry",
    )

    # ── registry.route_entry ──────────────────────────────────────────────────
    op.create_table(
        "route_entry",
        sa.Column(
            "route_entry_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column("network_segment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("destination_cidr", postgresql.CIDR()),
        sa.Column("gateway_ip", postgresql.INET()),
        sa.Column("device_name", sa.Text()),
        sa.Column("route_type_text", sa.Text()),
        sa.Column(
            "is_default_route",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("raw_route_text", sa.Text()),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["network_segment_id"],
            ["registry.network_segment.network_segment_id"],
            name="fk_route_entry_segment",
        ),
        schema="registry",
    )

    # ── registry.dns_resolver_state ────────────────────────────────────────────
    op.create_table(
        "dns_resolver_state",
        sa.Column(
            "dns_resolver_state_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column("resolver_list_text", sa.Text()),
        sa.Column("resolver_jsonb", postgresql.JSONB()),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="registry",
    )

    # ── registry.storage_asset ────────────────────────────────────────────────
    op.create_table(
        "storage_asset",
        sa.Column(
            "storage_asset_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "host_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.host.host_id"),
            nullable=False,
        ),
        sa.Column(
            "storage_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("device_name", sa.Text(), nullable=False),
        sa.Column("model_text", sa.Text()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("is_rotational", sa.Boolean()),
        sa.Column("filesystem_type_text", sa.Text()),
        sa.Column("mountpoint_text", sa.Text()),
        sa.Column("backing_device_text", sa.Text()),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery.collection_run.collection_run_id"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        schema="registry",
    )

    # ── registry.shared_service ───────────────────────────────────────────────
    op.create_table(
        "shared_service",
        sa.Column(
            "shared_service_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("service_code", sa.Text(), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "service_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "environment_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column(
            "lifecycle_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text()),
        sa.Column("canonical_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["canonical_document_id"],
            ["docs.document.document_id"],
            name="fk_shared_service_canonical_document",
        ),
        schema="registry",
    )

    # ── registry.service_instance ─────────────────────────────────────────────
    op.create_table(
        "service_instance",
        sa.Column(
            "service_instance_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "shared_service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.shared_service.shared_service_id"),
            nullable=False,
        ),
        sa.Column("host_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "runtime_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("instance_name", sa.Text(), nullable=False),
        sa.Column("container_name", sa.Text()),
        sa.Column("systemd_unit_name", sa.Text()),
        sa.Column("compose_project_name", sa.Text()),
        sa.Column("image_reference", sa.Text()),
        sa.Column("version_text", sa.Text()),
        sa.Column(
            "status_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(
            ["host_id"],
            ["registry.host.host_id"],
            name="fk_service_instance_host",
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_service_instance_run",
        ),
        schema="registry",
    )

    # ── registry.service_exposure ─────────────────────────────────────────────
    op.create_table(
        "service_exposure",
        sa.Column(
            "service_exposure_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "service_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.service_instance.service_instance_id"),
            nullable=False,
        ),
        sa.Column(
            "exposure_method_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("design_source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hostname", sa.Text()),
        sa.Column("host_ip", postgresql.INET()),
        sa.Column("listen_port", sa.Integer()),
        sa.Column("backend_host", sa.Text()),
        sa.Column("backend_port", sa.Integer()),
        sa.Column("protocol_text", sa.Text()),
        sa.Column("sni_hostname", sa.Text()),
        sa.Column("path_prefix", sa.Text()),
        sa.Column(
            "is_external",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "is_declared_in_design",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "is_tls_terminated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("is_live_probe_success", sa.Boolean()),
        sa.Column("observed_health_term_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("probe_confidence_score", sa.Numeric(5, 4)),
        sa.Column("last_probe_result_text", sa.Text()),
        sa.Column("last_probe_checked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(
            ["design_source_document_id"],
            ["docs.document.document_id"],
            name="fk_service_exposure_design_doc",
        ),
        sa.ForeignKeyConstraint(
            ["observed_health_term_id"],
            ["taxonomy.taxonomy_term.taxonomy_term_id"],
            name="fk_service_exposure_health_term",
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_service_exposure_run",
        ),
        schema="registry",
    )

    # ── registry.service_dependency ───────────────────────────────────────────
    op.create_table(
        "service_dependency",
        sa.Column(
            "service_dependency_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_service_instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registry.service_instance.service_instance_id"),
            nullable=False,
        ),
        sa.Column(
            "target_service_instance_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "target_shared_service_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "relationship_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("dependency_role_text", sa.Text()),
        sa.Column(
            "is_hard_dependency",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("evidence_confidence", sa.Numeric(5, 4)),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_at", sa.TIMESTAMP(timezone=True)),
        sa.ForeignKeyConstraint(
            ["target_service_instance_id"],
            ["registry.service_instance.service_instance_id"],
            name="fk_service_dep_target_instance",
        ),
        sa.ForeignKeyConstraint(
            ["target_shared_service_id"],
            ["registry.shared_service.shared_service_id"],
            name="fk_service_dep_target_shared",
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_service_dependency_run",
        ),
        schema="registry",
    )

    # ── registry.ownership_assignment ─────────────────────────────────────────
    op.create_table(
        "ownership_assignment",
        sa.Column(
            "ownership_assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "owner_type_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("owner_code", sa.Text(), nullable=False),
        sa.Column("responsibility_text", sa.Text()),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True)),
        schema="registry",
    )

    # Add deferred FKs for cluster.canonical_document_id
    op.create_foreign_key(
        "fk_cluster_canonical_document",
        "cluster",
        "document",
        ["canonical_document_id"],
        ["document_id"],
        source_schema="registry",
        referent_schema="docs",
    )

    # ── retrieval.document_chunk ──────────────────────────────────────────────
    op.create_table(
        "document_chunk",
        sa.Column(
            "document_chunk_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("docs.document_version.document_version_id"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_hash", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer()),
        sa.Column("section_path_text", sa.Text()),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="retrieval",
    )

    # ── retrieval.chunk_embedding ─────────────────────────────────────────────
    # NOTE: embedding_vector is TEXT here; ALTER to vector(1536) via migration
    #       0002_enable_pgvector after enabling the pgvector extension on the server.
    op.create_table(
        "chunk_embedding",
        sa.Column(
            "chunk_embedding_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("retrieval.document_chunk.document_chunk_id"),
            nullable=False,
        ),
        sa.Column("embedding_model_code", sa.Text(), nullable=False),
        sa.Column("embedding_vector", sa.Text()),
        sa.Column("lexical_tsv", postgresql.TSVECTOR()),
        sa.Column("summary_text", sa.Text()),
        sa.Column("metadata_jsonb", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="retrieval",
    )

    # ── retrieval.evidence_pack ───────────────────────────────────────────────
    op.create_table(
        "evidence_pack",
        sa.Column(
            "evidence_pack_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("pack_code", sa.Text(), unique=True, nullable=False),
        sa.Column("task_type_code", sa.Text(), nullable=False),
        sa.Column("request_scope_jsonb", postgresql.JSONB()),
        sa.Column("selection_rationale_text", sa.Text()),
        sa.Column("token_budget", sa.Integer()),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="retrieval",
    )

    # ── retrieval.evidence_pack_item ──────────────────────────────────────────
    op.create_table(
        "evidence_pack_item",
        sa.Column(
            "evidence_pack_item_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "evidence_pack_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("retrieval.evidence_pack.evidence_pack_id"),
            nullable=False,
        ),
        sa.Column("item_order", sa.Integer(), nullable=False),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("inclusion_reason_text", sa.Text()),
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["retrieval.document_chunk.document_chunk_id"],
            name="fk_evidence_pack_item_chunk",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_artifact_id"],
            ["discovery.evidence_artifact.evidence_artifact_id"],
            name="fk_evidence_pack_item_artifact",
        ),
        schema="retrieval",
    )

    # ── agent_control.prompt_template_registry ────────────────────────────────
    op.create_table(
        "prompt_template_registry",
        sa.Column(
            "prompt_template_registry_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("template_code", sa.Text(), unique=True, nullable=False),
        sa.Column("task_type_code", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Text(), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("policy_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_record_id"],
            ["governance.policy_record.policy_record_id"],
            name="fk_prompt_template_policy",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["docs.document_version.document_version_id"],
            name="fk_prompt_template_doc_version",
        ),
        schema="agent_control",
    )

    # ── agent_control.agent_run ───────────────────────────────────────────────
    op.create_table(
        "agent_run",
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_code", sa.Text(), unique=True, nullable=False),
        sa.Column("agent_identity", sa.Text(), nullable=False),
        sa.Column("task_type_code", sa.Text(), nullable=False),
        sa.Column(
            "prompt_template_registry_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("approval_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_scope_jsonb", postgresql.JSONB()),
        sa.Column(
            "status_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_registry_id"],
            ["agent_control.prompt_template_registry.prompt_template_registry_id"],
            name="fk_agent_run_prompt_template",
        ),
        sa.ForeignKeyConstraint(
            ["approval_record_id"],
            ["governance.approval_record.approval_record_id"],
            name="fk_agent_run_approval",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_pack_id"],
            ["retrieval.evidence_pack.evidence_pack_id"],
            name="fk_agent_run_evidence_pack",
        ),
        schema="agent_control",
    )

    # ── agent_control.action_request ──────────────────────────────────────────
    op.create_table(
        "action_request",
        sa.Column(
            "action_request_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("request_code", sa.Text(), unique=True, nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_class_text", sa.Text(), nullable=False),
        sa.Column("target_scope_jsonb", postgresql.JSONB()),
        sa.Column("requested_change_jsonb", postgresql.JSONB()),
        sa.Column(
            "status_text",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_control.agent_run.agent_run_id"],
            name="fk_action_request_agent_run",
        ),
        sa.ForeignKeyConstraint(
            ["approval_record_id"],
            ["governance.approval_record.approval_record_id"],
            name="fk_action_request_approval",
        ),
        schema="agent_control",
    )

    # ── agent_control.agent_evidence ──────────────────────────────────────────
    op.create_table(
        "agent_evidence",
        sa.Column(
            "agent_evidence_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_control.agent_run.agent_run_id"),
            nullable=False,
        ),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_role_text", sa.Text()),
        sa.Column("confidence_score", sa.Numeric(5, 4)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["document_chunk_id"],
            ["retrieval.document_chunk.document_chunk_id"],
            name="fk_agent_evidence_chunk",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_artifact_id"],
            ["discovery.evidence_artifact.evidence_artifact_id"],
            name="fk_agent_evidence_artifact",
        ),
        schema="agent_control",
    )

    # ── governance.change_log ─────────────────────────────────────────────────
    # Created last because it references agent_control.action_request
    op.create_table(
        "change_log",
        sa.Column(
            "change_log_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("change_code", sa.Text(), unique=True, nullable=False),
        sa.Column(
            "entity_kind_term_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomy.taxonomy_term.taxonomy_term_id"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("change_source_text", sa.Text(), nullable=False),
        sa.Column("change_summary_text", sa.Text(), nullable=False),
        sa.Column("action_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("collection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reconciliation_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canonical_document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("before_state_jsonb", postgresql.JSONB()),
        sa.Column("after_state_jsonb", postgresql.JSONB()),
        sa.Column("rollback_reference_text", sa.Text()),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["action_request_id"],
            ["agent_control.action_request.action_request_id"],
            name="fk_change_log_action_request",
        ),
        sa.ForeignKeyConstraint(
            ["approval_record_id"],
            ["governance.approval_record.approval_record_id"],
            name="fk_change_log_approval",
        ),
        sa.ForeignKeyConstraint(
            ["collection_run_id"],
            ["discovery.collection_run.collection_run_id"],
            name="fk_change_log_collection_run",
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_result_id"],
            ["discovery.reconciliation_result.reconciliation_result_id"],
            name="fk_change_log_reconciliation",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_document_version_id"],
            ["docs.document_version.document_version_id"],
            name="fk_change_log_doc_version",
        ),
        schema="governance",
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("change_log", schema="governance")
    op.drop_table("agent_evidence", schema="agent_control")
    op.drop_table("action_request", schema="agent_control")
    op.drop_table("agent_run", schema="agent_control")
    op.drop_table("prompt_template_registry", schema="agent_control")
    op.drop_table("evidence_pack_item", schema="retrieval")
    op.drop_table("evidence_pack", schema="retrieval")
    op.drop_table("chunk_embedding", schema="retrieval")
    op.drop_table("document_chunk", schema="retrieval")
    op.drop_table("ownership_assignment", schema="registry")
    op.drop_table("service_dependency", schema="registry")
    op.drop_table("service_exposure", schema="registry")
    op.drop_table("service_instance", schema="registry")
    op.drop_table("shared_service", schema="registry")
    op.drop_table("storage_asset", schema="registry")
    op.drop_table("dns_resolver_state", schema="registry")
    op.drop_table("route_entry", schema="registry")
    op.drop_table("ip_address_assignment", schema="registry")
    op.drop_table("network_interface", schema="registry")
    op.drop_table("network_segment", schema="registry")
    op.drop_table("gpu_device", schema="registry")
    op.drop_table("host_hardware_snapshot", schema="registry")
    op.drop_table("cluster_membership", schema="registry")
    op.drop_table("host_role_assignment", schema="registry")
    op.drop_table("host", schema="registry")
    op.drop_table("cluster", schema="registry")
    op.drop_table("approval_record", schema="governance")
    op.drop_table("policy_record", schema="governance")
    op.drop_table("reconciliation_result", schema="discovery")
    op.drop_table("evidence_artifact", schema="discovery")
    op.drop_table("observed_fact", schema="discovery")
    op.drop_table("collection_run", schema="discovery")
    op.drop_table("discovery_source", schema="discovery")
    op.drop_table("document_entity_binding", schema="docs")
    op.drop_table("document_version", schema="docs")
    op.drop_table("document", schema="docs")
    op.drop_table("taxonomy_term", schema="taxonomy")
    op.drop_table("taxonomy_domain", schema="taxonomy")

    for schema in reversed(_SCHEMAS):
        op.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
