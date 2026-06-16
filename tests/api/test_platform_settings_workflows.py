import os
import tempfile
from uuid import uuid4

import pytest
from dimoo_run.api.dependencies import (
    default_api_key_authenticator,
    reset_api_key_authenticator,
)
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    AuditLog,
    ContainerPoolPolicy,
    Environment,
    ObservabilityExporter,
    PlatformControlSetting,
    Project,
    SandboxPolicy,
    SemanticStoreProvider,
    Tenant,
)
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.platform.settings_snapshot import write_scoped_setting
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture(autouse=True)
def configure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "dev")
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    monkeypatch.setenv("DIMOORUN_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    monkeypatch.setenv("DIMOORUN_MODEL_GATEWAY_PROVIDER", "newapi")
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-platform-settings-{uuid4().hex}.db",
    )
    reset_api_key_authenticator()


def create_api_key(scopes: set[str] | None = None) -> str:
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        Base.metadata.create_all(session.get_bind())
        tenant = session.get(Tenant, 1)
        if tenant is None:
            tenant = Tenant(id=1, name="Default Tenant", slug="default-tenant", status="active")
            session.add(tenant)
            session.flush()
        project = session.get(Project, 1)
        if project is None:
            project = Project(
                id=1,
                tenant_id=1,
                name="Default Project",
                slug="default-project",
                status="active",
            )
            session.add(project)
            session.flush()
        existing_environment = session.scalar(
            select(Environment).where(
                Environment.tenant_id == 1,
                Environment.project_id == 1,
                Environment.environment == "production",
            )
        )
        if existing_environment is None:
            session.add(
                Environment(
                    tenant_id=1,
                    project_id=1,
                    name="production",
                    environment="production",
                    status="active",
                    metadata_json={"seeded": True},
                )
            )
        session.commit()
    authenticator = default_api_key_authenticator()
    account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="platform-ops",
        permissions=scopes or {"*", "agent:read", "admin:write"},
        created_by="bootstrap",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="platform-ops-key",
        owner_type="service_account",
        owner_id=account.id,
        scopes=scopes or {"*", "agent:read", "admin:write"},
        created_by="bootstrap",
    )
    return plain_key


def headers(api_key: str, *, request_id: str = "req_platform_settings") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "production",
        "X-Audit-Reason": "platform settings workflow",
    }


def test_platform_settings_console_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    assert "/v1/console/settings/platform" in paths
    assert "/v1/console/settings/providers" in paths
    assert "/v1/console/settings/scoped-defaults" in paths
    assert "/v1/console/settings/scoped-defaults/{scope_kind}" in paths
    assert "/v1/console/settings/danger/preflight" in paths
    assert "/v1/console/settings/danger/actions/{action}" in paths


def test_settings_snapshot_reports_platform_mode_and_safety() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()

    response = client.get("/v1/console/settings/platform", headers=headers(api_key))

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["runtime_mode"] == "dev"
    assert item["database_mode"] == "sqlite"
    assert item["queue_backend"] == "redis"
    assert item["secret_provider"]["provider"] == "vault"
    assert item["model_gateway_provider"]["provider"] == "newapi"
    assert item["production_safety"]["status"] == "safe"
    assert [entry["scope_kind"] for entry in item["scope_defaults"]] == [
        "organization",
        "project",
        "environment",
    ]


def test_provider_status_reflects_configured_outage_and_exporter_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        session.add(
            ObservabilityExporter(
                tenant_id=1,
                project_id=1,
                name="otel",
                exporter_type="otlp",
                target_ref="http://otel:4318",
                status="active",
                metadata_json={},
            )
        )
        session.commit()

    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "memory")
    response = client.get("/v1/console/settings/providers", headers=headers(api_key))

    assert response.status_code == 200
    items = {entry["provider"]: entry for entry in response.json()["items"]}
    assert items["postgres"]["status"] == "degraded"
    assert items["secret_provider"]["status"] == "offline"
    assert items["observability_exporter"]["status"] == "healthy"


def test_scoped_default_update_persists_environment_change() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()

    response = client.post(
        "/v1/console/settings/scoped-defaults/environment",
        headers=headers(api_key),
        json={"config": {"default_deployment_strategy": "blue_green"}},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["scope_kind"] == "environment"
    assert item["config"]["default_deployment_strategy"] == "blue_green"

    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        record = session.scalar(
            select(PlatformControlSetting).where(
                PlatformControlSetting.scope_kind == "environment",
                PlatformControlSetting.environment == "production",
            )
        )
        assert record is not None
        assert record.config_json["default_deployment_strategy"] == "blue_green"


def test_production_read_only_blocks_organization_default_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    create_api_key()
    settings = Settings.from_env()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])

    with session_factory() as session:
        with pytest.raises(ValueError) as exc_info:
            write_scoped_setting(
                session,
                settings=settings,
                tenant_id=1,
                project_id=1,
                environment="production",
                scope_kind="organization",
                config={"default_queue": "priority"},
                actor_id="operator_1",
                request_id="req_platform_settings_readonly",
                audit_reason="platform settings workflow",
            )

    assert "Production mode only allows environment-scoped defaults to change." in str(
        exc_info.value
    )


def test_dangerous_action_preflight_blocks_unhealthy_provider_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "memory")
    client = TestClient(create_app())
    api_key = create_api_key()

    response = client.post(
        "/v1/console/settings/danger/preflight",
        headers=headers(api_key),
        json={"action": "rotate_object_store_credentials"},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["available"] is False
    assert "not healthy enough for this action" in item["blocked_reasons"][0]
    assert item["affected_resources"] == [
        {"label": "Deployments", "count": 0},
        {"label": "Published surfaces", "count": 0},
        {"label": "Workers", "count": 0},
    ]


def test_dangerous_action_freezes_environment_and_writes_audit() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()

    preview = client.post(
        "/v1/console/settings/danger/preflight",
        headers=headers(api_key, request_id="req_platform_preflight"),
        json={"action": "freeze_environment_writes"},
    )
    assert preview.status_code == 200
    assert preview.json()["item"]["affected_resources"] == [
        {"label": "Deployments", "count": 0},
        {"label": "Published surfaces", "count": 0},
        {"label": "Workers", "count": 0},
    ]
    confirmation = preview.json()["item"]["confirmation_phrase"]

    response = client.post(
        "/v1/console/settings/danger/actions/freeze_environment_writes",
        headers=headers(api_key, request_id="req_platform_apply"),
        json={
            "confirmation": confirmation,
            "rollback_notes": "Unfreeze once the migration finishes.",
        },
    )

    assert response.status_code == 200
    assert response.json()["item"]["status"] == "applied"

    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        environment_setting = session.scalar(
            select(PlatformControlSetting).where(
                PlatformControlSetting.scope_kind == "environment",
                PlatformControlSetting.environment == "production",
            )
        )
        assert environment_setting is not None
        assert environment_setting.config_json["freeze_writes"] is True
        audit = session.scalar(
            select(AuditLog)
            .where(AuditLog.request_id == "req_platform_apply")
            .order_by(AuditLog.created_at.desc())
        )
        assert audit is not None
        assert audit.action == "platform.settings.environment.update"


def test_observability_exporter_validation_redacts_target_and_records_proof() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        session.add(
            ObservabilityExporter(
                id=1,
                tenant_id=1,
                project_id=1,
                name="primary-otel",
                exporter_type="otlp",
                target_ref="http://otel.internal:4318",
                status="active",
                metadata_json={"blocked_reason": None},
            )
        )
        session.commit()

    response = client.post(
        "/v1/console/settings/observability-exporters/1/validate",
        headers=headers(api_key, request_id="req_exporter_validate"),
        json={"audit_reason": "verify exporter"},
    )

    assert response.status_code == 200
    body = response.json()["item"]
    assert body["validation_status"] in {"reachable", "blocked", "unconfigured"}
    assert body["request_id"] == "req_exporter_validate"
    assert "internal" not in body["target_ref_redacted"]


def test_semantic_store_provider_validation_reports_index_coverage() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        session.add(
            SemanticStoreProvider(
                id=1,
                tenant_id=1,
                project_id=1,
                name="tenant-memory",
                embedding_model="text-embedding-3-large",
                connection_ref="postgresql://vector-store",
                status="active",
                metadata_json={"index_coverage": {"runs": 92, "artifacts": 81}},
            )
        )
        session.commit()

    response = client.post(
        "/v1/console/settings/semantic-store-providers/1/validate",
        headers=headers(api_key, request_id="req_semantic_provider_validate"),
        json={"audit_reason": "verify semantic store"},
    )

    assert response.status_code == 200
    body = response.json()["item"]
    assert body["provider_status"] in {"ready", "degraded", "unconfigured"}
    assert "index_coverage" in body


def test_sandbox_policy_preview_reports_blocked_capabilities() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        session.add(
            SandboxPolicy(
                id=1,
                tenant_id=1,
                project_id=1,
                name="restricted-egress",
                isolation_level="container",
                network_policy="deny_all",
                filesystem_policy="read_only",
                status="active",
                metadata_json={"affected_surfaces": ["published_surfaces", "replay_jobs"]},
            )
        )
        session.commit()

    response = client.post(
        "/v1/console/settings/sandbox-policies/1/preview",
        headers=headers(api_key, request_id="req_sandbox_preview"),
        json={"capabilities": ["network", "filesystem"], "audit_reason": "preview sandbox"},
    )

    assert response.status_code == 200
    body = response.json()["item"]
    assert "blocked_capabilities" in body
    assert body["audit_required"] is True


def test_container_pool_policy_estimate_reports_capacity_impact() -> None:
    client = TestClient(create_app())
    api_key = create_api_key()
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        session.add(
            ContainerPoolPolicy(
                id=1,
                tenant_id=1,
                project_id=1,
                name="default-pool",
                max_containers=6,
                cpu_limit="1000m",
                memory_limit="1Gi",
                idle_timeout_seconds=300,
                status="active",
                metadata_json={"warm_capacity": 2, "worker_pools": ["default", "gpu-burst"]},
            )
        )
        session.commit()

    response = client.post(
        "/v1/console/settings/container-pool-policies/1/estimate",
        headers=headers(api_key, request_id="req_container_pool_estimate"),
        json={"requested_workers": 4, "audit_reason": "estimate pool"},
    )

    assert response.status_code == 200
    body = response.json()["item"]
    assert "warm_capacity" in body
    assert "scale_limit" in body
    assert body["request_id"] == "req_container_pool_estimate"
