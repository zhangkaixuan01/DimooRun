from dimoo_run.domain.enums import (
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
    RunStatus,
    TaskStatus,
)
from dimoo_run.domain.models import Deployment, Run, Task
from dimoo_run.persistence.database import Base
from sqlalchemy import inspect

REQUIRED_TABLES = {
    "tenants",
    "projects",
    "users",
    "service_accounts",
    "roles",
    "permissions",
    "api_keys",
    "agents",
    "agent_versions",
    "deployments",
    "agent_instances",
    "sessions",
    "runs",
    "run_attempts",
    "tasks",
    "events",
    "checkpoint_indexes",
    "tools",
    "secrets",
    "audit_logs",
    "published_surfaces",
    "ingress_routes",
    "catalog_items",
    "prompt_assets",
    "config_assets",
    "templates",
    "run_graph_nodes",
    "run_graph_edges",
    "datasets",
    "dataset_items",
    "experiments",
    "experiment_runs",
    "evaluation_results",
    "feedback",
    "scheduled_runs",
    "batch_runs",
    "replay_jobs",
    "memory_blocks",
    "semantic_store_providers",
    "model_gateways",
    "model_policies",
    "model_usage_snapshots",
    "policies",
    "policy_decisions",
    "human_tasks",
    "approval_requests",
    "approval_policies",
    "artifacts",
    "notification_channels",
    "alert_rules",
    "incident_events",
    "webhook_subscriptions",
    "extensions",
    "backup_plans",
    "restore_jobs",
}


def test_all_required_tables_are_registered() -> None:
    assert REQUIRED_TABLES <= set(Base.metadata.tables)


def test_core_foreign_keys_are_present() -> None:
    agent_version_fks = {
        fk.column.table.name for fk in Base.metadata.tables["agent_versions"].foreign_keys
    }
    deployment_fks = {
        fk.column.table.name for fk in Base.metadata.tables["deployments"].foreign_keys
    }
    run_fks = {fk.column.table.name for fk in Base.metadata.tables["runs"].foreign_keys}

    assert "agents" in agent_version_fks
    assert {"agents", "agent_versions", "tenants", "projects"} <= deployment_fks
    assert {"agents", "agent_versions", "tenants", "projects"} <= run_fks


def test_status_defaults_match_design_spec() -> None:
    assert Deployment.__table__.c.desired_status.default is not None
    assert Deployment.__table__.c.desired_status.default.arg == DeploymentDesiredStatus.draft.value
    assert Deployment.__table__.c.runtime_status.default is not None
    runtime_status_default = Deployment.__table__.c.runtime_status.default
    assert runtime_status_default.arg == DeploymentRuntimeStatus.not_loaded.value
    assert Run.__table__.c.status.default is not None
    assert Run.__table__.c.status.default.arg == RunStatus.pending.value
    assert Task.__table__.c.status.default is not None
    assert Task.__table__.c.status.default.arg == TaskStatus.queued.value


def test_metadata_tables_can_be_created_in_sqlite() -> None:
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert REQUIRED_TABLES <= set(inspector.get_table_names())
