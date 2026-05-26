from typing import cast

from dimoo_run.domain.enums import (
    DeploymentDesiredStatus,
    DeploymentRuntimeStatus,
    RunStatus,
    TaskStatus,
)
from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    APIKey,
    AuditLog,
    Deployment,
    IdempotencyRecord,
    IngressRoute,
    Project,
    PublishedSurface,
    Run,
    Task,
)
from dimoo_run.persistence.database import Base
from sqlalchemy import DateTime, Table, inspect

REQUIRED_TABLES = {
    "tenants",
    "projects",
    "users",
    "service_accounts",
    "roles",
    "permissions",
    "api_keys",
    "idempotency_records",
    "execution_profiles",
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


def test_all_domain_tables_have_audit_and_soft_delete_columns() -> None:
    required_columns = {
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
        "is_deleted",
        "deleted_at",
        "deleted_by",
    }

    for table_name in REQUIRED_TABLES:
        assert required_columns <= set(Base.metadata.tables[table_name].columns.keys()), table_name


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


def test_metadata_tables_have_tenant_and_project_foreign_keys() -> None:
    metadata_tables = REQUIRED_TABLES - {
        "tenants",
        "projects",
        "users",
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
        "execution_profiles",
        "audit_logs",
        "idempotency_records",
    }

    for table_name in metadata_tables:
        foreign_key_tables = {
            foreign_key.column.table.name
            for foreign_key in Base.metadata.tables[table_name].foreign_keys
        }
        assert {"tenants", "projects"} <= foreign_key_tables, table_name


def test_critical_uniqueness_constraints_are_present() -> None:
    expected_constraints = {
        Project: "uq_projects_tenant_slug",
        APIKey: "uq_api_keys_key_hash",
        AgentVersion: "uq_agent_versions_agent_version",
        IdempotencyRecord: "uq_idempotency_records_scope_key",
    }

    for model, constraint_name in expected_constraints.items():
        table = cast(Table, model.__table__)
        assert constraint_name in {
            constraint.name for constraint in table.constraints
        }, model.__tablename__


def test_soft_deleted_resources_do_not_block_active_unique_names() -> None:
    expected_indexes = {
        Agent: "uq_agents_project_name_active",
        Deployment: "uq_deployments_project_environment_agent_active",
    }

    for model, index_name in expected_indexes.items():
        table = cast(Table, model.__table__)
        indexes = {index.name: index for index in table.indexes}
        assert index_name in indexes, model.__tablename__
        index = indexes[index_name]
        assert index.unique is True
        assert "is_deleted" in str(index.dialect_options["postgresql"]["where"])
        assert "is_deleted" in str(index.dialect_options["sqlite"]["where"])


def test_audit_log_keeps_columns_but_is_marked_immutable() -> None:
    audit_log_table = cast(Table, AuditLog.__table__)
    assert audit_log_table.info["immutable"] is True
    assert "is_deleted" in audit_log_table.columns


def test_audit_fields_come_from_shared_mixins_only() -> None:
    for model in [Run, Task, AuditLog, AgentVersion]:
        assert list(model.__table__.columns.keys()).count("created_at") == 1
        assert list(model.__table__.columns.keys()).count("created_by") == 1


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


def test_agent_version_records_adapter_contract_versions() -> None:
    columns = AgentVersion.__table__.columns

    for column_name in [
        "adapter_api_version",
        "framework_version",
        "manifest_schema_version",
        "capability_schema_version",
        "event_schema_version",
        "compatibility_status",
        "compatibility_checked_at",
    ]:
        assert column_name in columns


def test_runtime_tables_include_scheduler_and_streaming_columns() -> None:
    task_columns = Task.__table__.columns
    event_columns = Base.metadata.tables["events"].columns

    assert "fencing_token" in task_columns
    assert "sequence" in event_columns
    assert "event_id" in event_columns
    assert event_columns["sequence"].nullable is False
    assert event_columns["event_id"].nullable is False
    assert "uq_events_run_sequence" in {
        constraint.name for constraint in Base.metadata.tables["events"].constraints
    }


def test_published_surface_and_ingress_route_tables_are_hardened() -> None:
    surface_table = cast(Table, PublishedSurface.__table__)
    route_table = cast(Table, IngressRoute.__table__)
    surface_columns = PublishedSurface.__table__.columns
    route_columns = IngressRoute.__table__.columns

    assert surface_table.info.get("placeholder") is not True
    assert route_table.info.get("placeholder") is not True
    for column_name in [
        "deployment_id",
        "type",
        "status",
    ]:
        assert column_name in surface_columns
    for column_name in [
        "surface_id",
        "path",
        "auth_mode",
        "rate_limit_policy_id",
        "access_log_enabled",
    ]:
        assert column_name in route_columns


def test_gateway_tables_have_active_uniqueness_indexes() -> None:
    surface_table = cast(Table, PublishedSurface.__table__)
    route_table = cast(Table, IngressRoute.__table__)

    surface_index = next(
        index
        for index in surface_table.indexes
        if index.name == "uq_published_surfaces_deployment_type_active"
    )
    route_index = next(
        index
        for index in route_table.indexes
        if index.name == "uq_ingress_routes_surface_path_active"
    )

    assert surface_index.unique is True
    assert "is_deleted" in str(surface_index.dialect_options["postgresql"]["where"])
    assert "is_deleted" in str(surface_index.dialect_options["sqlite"]["where"])
    assert route_index.unique is True
    assert "is_deleted" in str(route_index.dialect_options["postgresql"]["where"])
    assert "is_deleted" in str(route_index.dialect_options["sqlite"]["where"])


def test_governance_security_and_model_gateway_tables_are_hardened() -> None:
    hardened_columns = {
        "policies": {"type", "resource_type", "action", "decision", "priority", "condition_json"},
        "policy_decisions": {
            "policy_id",
            "resource_type",
            "resource_id",
            "action",
            "decision",
            "reason",
        },
        "model_gateways": {
            "name",
            "provider_type",
            "base_url",
            "credential_ref",
            "default_model_group",
        },
        "model_policies": {
            "gateway_id",
            "default_model",
            "allowed_models_json",
            "max_cost_per_run",
            "on_budget_exceeded",
        },
        "model_usage_snapshots": {
            "run_id",
            "attempt_id",
            "gateway_id",
            "model",
            "total_tokens",
            "cost",
            "currency",
        },
        "human_tasks": {"run_id", "type", "assignee_role", "payload_ref", "expires_at"},
        "approval_requests": {"human_task_id", "requested_by", "status", "decision_ref"},
        "approval_policies": {
            "name",
            "resource_type",
            "action",
            "risk_level",
            "required_role",
            "on_timeout",
        },
        "catalog_items": {
            "type",
            "name",
            "provider",
            "version",
            "schema_json",
            "risk_level",
        },
        "prompt_assets": {"name", "version", "content_ref", "variables_schema_json"},
        "config_assets": {"name", "version", "content_ref", "schema_json", "environment"},
        "templates": {"name", "version", "type", "content_ref"},
        "execution_profiles": {
            "name",
            "isolation_level",
            "network_policy",
            "filesystem_policy",
            "allowed_env_json",
        },
    }

    for table_name, columns in hardened_columns.items():
        table = Base.metadata.tables[table_name]
        assert table.info.get("placeholder") is not True, table_name
        assert columns <= set(table.columns.keys()), table_name


def test_governance_active_uniqueness_indexes_are_present() -> None:
    expected_indexes = {
        "catalog_items": "uq_catalog_items_scope_type_name_version_active",
        "prompt_assets": "uq_prompt_assets_scope_name_version_active",
        "config_assets": "uq_config_assets_scope_name_version_active",
        "templates": "uq_templates_scope_type_name_version_active",
        "model_gateways": "uq_model_gateways_scope_name_active",
        "execution_profiles": "uq_execution_profiles_scope_name_active",
    }

    for table_name, index_name in expected_indexes.items():
        indexes = {index.name: index for index in Base.metadata.tables[table_name].indexes}
        assert index_name in indexes, table_name
        assert indexes[index_name].unique is True


def test_observability_replay_and_quality_tables_are_hardened() -> None:
    hardened_columns = {
        "artifacts": {
            "run_id",
            "attempt_id",
            "event_id",
            "artifact_type",
            "mime_type",
            "size_bytes",
            "storage_uri",
            "checksum",
            "visibility_level",
            "retention_policy_id",
            "expires_at",
            "metadata_json",
        },
        "run_graph_nodes": {
            "run_id",
            "attempt_id",
            "node_key",
            "node_type",
            "framework_node_id",
            "name",
            "status",
            "latency_ms",
            "input_ref",
            "output_ref",
        },
        "run_graph_edges": {"run_id", "source_node_id", "target_node_id", "edge_type"},
        "datasets": {"name", "description", "source", "schema_json", "visibility_level"},
        "dataset_items": {
            "dataset_id",
            "source_run_id",
            "input_ref",
            "output_ref",
            "expected_ref",
        },
        "experiments": {
            "name",
            "agent_id",
            "baseline_agent_version_id",
            "candidate_agent_version_id",
            "dataset_id",
            "evaluator_config_json",
            "status",
        },
        "experiment_runs": {"experiment_id", "status", "started_at", "finished_at"},
        "evaluation_results": {
            "experiment_run_id",
            "evaluator_name",
            "score",
            "passed",
            "metadata_json",
        },
        "feedback": {"run_id", "source", "rating", "comment", "metadata_json"},
        "memory_blocks": {"agent_id", "memory_type", "content_ref", "metadata_json"},
        "semantic_store_providers": {
            "name",
            "embedding_model",
            "embedding_gateway_id",
            "connection_ref",
            "retention_policy_id",
            "status",
        },
        "notification_channels": {"type", "target_ref", "status", "metadata_json"},
        "alert_rules": {"name", "signal", "threshold", "channel_id", "status"},
        "incident_events": {"signal", "severity", "status", "source_ref", "value", "metadata_json"},
        "replay_jobs": {
            "source_run_id",
            "source_agent_version_id",
            "candidate_agent_version_id",
            "replay_run_id",
            "replay_task_id",
            "status",
            "requested_by",
            "override_config_json",
        },
    }

    for table_name, columns in hardened_columns.items():
        table = Base.metadata.tables[table_name]
        assert table.info.get("placeholder") is not True, table_name
        assert columns <= set(table.columns.keys()), table_name


def test_metadata_tables_can_be_created_in_sqlite() -> None:
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert REQUIRED_TABLES <= set(inspector.get_table_names())


def test_datetime_columns_are_timezone_aware() -> None:
    for table_name in REQUIRED_TABLES:
        table = Base.metadata.tables[table_name]
        assert cast(DateTime, table.c.created_at.type).timezone is True, table_name
        assert cast(DateTime, table.c.updated_at.type).timezone is True, table_name
        assert cast(DateTime, table.c.deleted_at.type).timezone is True, table_name

        for column in table.c:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True, f"{table_name}.{column.name}"


def test_placeholder_tables_are_marked_until_domain_fields_are_hardened() -> None:
    placeholder_tables = {
        "scheduled_runs",
        "batch_runs",
        "webhook_subscriptions",
        "extensions",
        "backup_plans",
        "restore_jobs",
    }

    for table_name in placeholder_tables:
        assert Base.metadata.tables[table_name].info["placeholder"] is True, table_name
