"""observability and quality tables

Revision ID: 0004_observability_quality
Revises: 0003_governance
Create Date: 2026-05-24
"""

from alembic import op
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)

from migrations.table_helpers import audit_columns, drop_tables, id_column, tenant_project_columns

revision = "0004_observability_quality"
down_revision = "0003_governance"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "run_graph_nodes",
    "run_graph_edges",
    "datasets",
    "dataset_items",
    "experiments",
    "experiment_runs",
    "evaluation_results",
    "feedback",
    "memory_blocks",
    "semantic_store_providers",
)


def upgrade() -> None:
    op.create_table(
        "run_graph_nodes",
        id_column(),
        *tenant_project_columns(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("attempt_id", String(64), ForeignKey("run_attempts.id")),
        Column("node_key", String(255), nullable=False),
        Column("node_type", String(64), nullable=False),
        Column("framework_node_id", String(255)),
        Column("name", String(255), nullable=False),
        Column("status", String(64), nullable=False, server_default="pending"),
        Column("started_at", DateTime(timezone=True)),
        Column("finished_at", DateTime(timezone=True)),
        Column("latency_ms", Integer),
        Column("input_ref", String(1024)),
        Column("output_ref", String(1024)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        UniqueConstraint("run_id", "node_key", name="uq_run_graph_nodes_run_node_key"),
        *audit_columns(),
    )
    op.create_table(
        "run_graph_edges",
        id_column(),
        *tenant_project_columns(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("source_node_id", String(64), ForeignKey("run_graph_nodes.id"), nullable=False),
        Column("target_node_id", String(64), ForeignKey("run_graph_nodes.id"), nullable=False),
        Column("edge_type", String(64), nullable=False),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "datasets",
        id_column(),
        *tenant_project_columns(),
        Column("name", String(255), nullable=False),
        Column("description", String),
        Column("source", String(64), nullable=False),
        Column("schema_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("visibility_level", String(64), nullable=False, server_default="internal"),
        *audit_columns(),
    )
    op.create_index(
        "uq_datasets_scope_name_active",
        "datasets",
        ["tenant_id", "project_id", "name"],
        unique=True,
        sqlite_where=text("is_deleted = 0"),
        postgresql_where=text("is_deleted = false"),
    )
    op.create_table(
        "dataset_items",
        id_column(),
        *tenant_project_columns(),
        Column("dataset_id", String(64), ForeignKey("datasets.id"), nullable=False),
        Column("source_run_id", String(64), ForeignKey("runs.id")),
        Column("input_ref", String(1024), nullable=False),
        Column("output_ref", String(1024)),
        Column("expected_ref", String(1024)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "experiments",
        id_column(),
        *tenant_project_columns(),
        Column("name", String(255), nullable=False),
        Column("agent_id", String(64), ForeignKey("agents.id"), nullable=False),
        Column("baseline_agent_version_id", String(64), ForeignKey("agent_versions.id")),
        Column(
            "candidate_agent_version_id",
            String(64),
            ForeignKey("agent_versions.id"),
            nullable=False,
        ),
        Column("dataset_id", String(64), ForeignKey("datasets.id"), nullable=False),
        Column("evaluator_config_json", JSON, nullable=False, server_default=text("'{}'")),
        Column("status", String(64), nullable=False, server_default="draft"),
        *audit_columns(),
    )
    op.create_table(
        "experiment_runs",
        id_column(),
        *tenant_project_columns(),
        Column("experiment_id", String(64), ForeignKey("experiments.id"), nullable=False),
        Column("status", String(64), nullable=False, server_default="running"),
        Column("started_at", DateTime(timezone=True)),
        Column("finished_at", DateTime(timezone=True)),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "evaluation_results",
        id_column(),
        *tenant_project_columns(),
        Column(
            "experiment_run_id",
            String(64),
            ForeignKey("experiment_runs.id"),
            nullable=False,
        ),
        Column("evaluator_name", String(255), nullable=False),
        Column("score", Float, nullable=False),
        Column("passed", Boolean, nullable=False),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "feedback",
        id_column(),
        *tenant_project_columns(),
        Column("run_id", String(64), ForeignKey("runs.id"), nullable=False),
        Column("source", String(64), nullable=False),
        Column("rating", String(64)),
        Column("comment", String),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "memory_blocks",
        id_column(),
        *tenant_project_columns(),
        Column("agent_id", String(64), ForeignKey("agents.id")),
        Column("memory_type", String(64), nullable=False),
        Column("content_ref", String(1024), nullable=False),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )
    op.create_table(
        "semantic_store_providers",
        id_column(),
        *tenant_project_columns(),
        Column("name", String(255), nullable=False),
        Column("embedding_model", String(255), nullable=False),
        Column("embedding_gateway_id", String(64), ForeignKey("model_gateways.id")),
        Column("connection_ref", String(512), nullable=False),
        Column("retention_policy_id", String(64)),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )


def downgrade() -> None:
    drop_tables(TABLE_NAMES)
