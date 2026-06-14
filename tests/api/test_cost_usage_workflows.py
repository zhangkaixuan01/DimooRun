import os
import tempfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from dimoo_run.api.admin.notifications import (
    list_delivery_attempts,
    reset_notification_workflows,
)
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.deployments import reset_deployment_control
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.domain.models import (
    AuditLog,
    CostBudgetPolicy,
    CostSavedView,
    Deployment,
    ModelUsageSnapshot,
    NotificationChannel,
    Run,
)
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import Base
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

_ORIGINAL_ENV: dict[str, str | None] = {}


def setup_function() -> None:
    global _ORIGINAL_ENV
    _ORIGINAL_ENV = {
        "DIMOORUN_RUNTIME_MODE": os.environ.get("DIMOORUN_RUNTIME_MODE"),
        "DIMOORUN_NATIVE_RUNTIME_STORE": os.environ.get("DIMOORUN_NATIVE_RUNTIME_STORE"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
    }
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_NATIVE_RUNTIME_STORE"] = "sqlalchemy"
    os.environ["DATABASE_URL"] = (
        f"sqlite:///{tempfile.gettempdir()}/dimoorun-costs-{uuid4().hex}.db"
    )
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()
    reset_notification_workflows()
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(engine)


def teardown_function() -> None:
    reset_api_key_authenticator()
    reset_deployment_control()
    reset_native_runtime()
    reset_notification_workflows()
    for key, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def create_api_key(*, scopes: set[str]) -> str:
    authenticator = default_api_key_authenticator()
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="cost-workflows",
        permissions=scopes,
        created_by="admin_1",
    )
    plain_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="cost-workflows-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    return plain_key


def auth_headers(
    api_key: str,
    *,
    environment: str = "production",
    request_id: str = "req_cost_workflows",
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": environment,
    }


def create_deployment(client: TestClient, api_key: str, *, environment: str) -> int:
    agent = client.post(
        "/v1/agents",
        headers=auth_headers(api_key, environment=environment),
        json={"name": f"support-agent-{environment}"},
    )
    assert agent.status_code == 201
    agent_id = agent.json()["id"]
    version = client.post(
        f"/v1/agents/{agent_id}/versions",
        headers=auth_headers(api_key, environment=environment),
        json={
            "version": "0.1.0",
            "package_uri": f"file://support-agent-{environment}",
            "framework": "langgraph",
            "adapter": "langgraph",
            "entrypoint": "agent:create_agent",
            "manifest": {
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create_agent",
                },
                "capabilities": {"invoke": True},
                "validation_token": validation_token(
                    package_uri=f"file://support-agent-{environment}",
                    framework="langgraph",
                    adapter="langgraph",
                    entrypoint="agent:create_agent",
                    manifest={
                        "runtime": {
                            "framework": "langgraph",
                            "adapter": "langgraph",
                            "entrypoint": "agent:create_agent",
                        },
                        "capabilities": {"invoke": True},
                    },
                ),
            },
            "status": "ready",
        },
    )
    assert version.status_code == 201
    deployment = client.post(
        "/v1/deployments",
        headers=auth_headers(api_key, environment=environment),
        json={
            "agent_id": agent_id,
            "agent_version_id": version.json()["id"],
            "environment": environment,
            "desired_status": "active",
            "replicas": 1,
        },
    )
    assert deployment.status_code == 201
    return int(deployment.json()["id"])


def submit_task(
    client: TestClient,
    api_key: str,
    *,
    deployment_id: int,
    environment: str,
    suffix: str,
) -> int:
    task = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(
            api_key,
            environment=environment,
            request_id=f"req_cost_task_{suffix}",
        )
        | {"Idempotency-Key": f"idem_cost_{suffix}"},
        json={"input": {"message": suffix}},
    )
    assert task.status_code == 202
    return int(task.json()["run_id"])


def update_run_and_usage(
    *,
    run_id: int,
    status: str,
    cost: float,
    total_tokens: int,
    provider: str,
    model: str,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        run.status = status
        run.started_at = datetime.now(UTC) - timedelta(seconds=5)
        run.finished_at = datetime.now(UTC)
        run.error = "provider timeout" if status == "failed" else None
        session.add(
            ModelUsageSnapshot(
                tenant_id=1,
                project_id=1,
                run_id=run_id,
                attempt_id=None,
                gateway_id=1,
                gateway_request_id=f"gw_{run_id}",
                model=model,
                provider=provider,
                prompt_tokens=total_tokens // 2,
                completion_tokens=total_tokens // 2,
                total_tokens=total_tokens,
                cost=cost,
                currency="USD",
                raw_usage_json={"cost": cost, "total_tokens": total_tokens},
            )
        )
        session.commit()


def create_budget_policy(
    *,
    environment: str,
    scope_type: str,
    scope_ref: str | None,
    threshold_usd: float,
    action_mode: str,
    channel_target: str = "slack:#ops-finops",
) -> int:
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        channel = NotificationChannel(
            tenant_id=1,
            project_id=1,
            type="webhook",
            target_ref=channel_target,
            status="active",
            metadata_json={},
        )
        session.add(channel)
        session.flush()
        policy = CostBudgetPolicy(
            tenant_id=1,
            project_id=1,
            name=f"{scope_type}-{action_mode}-guardrail",
            environment=environment,
            scope_type=scope_type,
            scope_ref=scope_ref,
            threshold_usd=threshold_usd,
            reset_window="monthly",
            channel_id=channel.id,
            action_mode=action_mode,
            status="active",
            metadata_json={},
        )
        session.add(policy)
        session.commit()
        return int(policy.id)


def create_saved_cost_view(
    *,
    environment: str,
    name: str,
    group_by: str,
    window_days: int,
    filters: dict[str, object] | None = None,
) -> int:
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        view = CostSavedView(
            tenant_id=1,
            project_id=1,
            name=name,
            environment=environment,
            group_by=group_by,
            window_days=window_days,
            filters_json=filters or {},
            status="active",
            metadata_json={},
        )
        session.add(view)
        session.commit()
        return int(view.id)


def attach_deployment_quality_gate(
    *,
    deployment_id: int,
    experiment_run_id: int,
    candidate_agent_version_id: int,
    status: str,
    promotion_allowed: bool,
    average_score: float,
    min_score: float,
    blocked_reason: str | None = None,
) -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        deployment = session.get(Deployment, deployment_id)
        assert deployment is not None
        deployment.config_json = {
            **dict(deployment.config_json or {}),
            "promotion": {
                "current_agent_version_id": candidate_agent_version_id,
                "experiment_run_id": experiment_run_id,
                "quality_gate": {
                    "status": status,
                    "promotion_allowed": promotion_allowed,
                    "blocked_reason": blocked_reason,
                    "required_evidence": ["experiment_run", "evaluation_results"],
                    "evidence": {
                        "experiment_run_id": experiment_run_id,
                        "candidate_agent_version_id": candidate_agent_version_id,
                        "average_score": average_score,
                        "min_score": min_score,
                    },
                },
            },
        }
        session.commit()


def test_cost_console_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    assert "/v1/console/costs/summary" in paths
    assert "/v1/console/costs/anomalies" in paths
    assert "/v1/console/costs/budgets/preview" in paths
    assert "/v1/console/costs/budgets/{policy_id}/preview" in paths
    assert "/v1/console/costs/views/{view_id}" in paths


def test_cost_summary_is_scoped_by_environment_and_grouping() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    production_deployment = create_deployment(client, api_key, environment="production")
    staging_deployment = create_deployment(client, api_key, environment="staging")
    prod_run_1 = submit_task(
        client,
        api_key,
        deployment_id=production_deployment,
        environment="production",
        suffix="prod_1",
    )
    prod_run_2 = submit_task(
        client,
        api_key,
        deployment_id=production_deployment,
        environment="production",
        suffix="prod_2",
    )
    staging_run = submit_task(
        client,
        api_key,
        deployment_id=staging_deployment,
        environment="staging",
        suffix="staging_1",
    )
    update_run_and_usage(
        run_id=prod_run_1,
        status="succeeded",
        cost=0.10,
        total_tokens=100,
        provider="openai",
        model="gpt-4.1-mini",
    )
    update_run_and_usage(
        run_id=prod_run_2,
        status="failed",
        cost=1.20,
        total_tokens=600,
        provider="openai",
        model="gpt-4.1",
    )
    update_run_and_usage(
        run_id=staging_run,
        status="succeeded",
        cost=3.00,
        total_tokens=900,
        provider="anthropic",
        model="claude-3-7-sonnet",
    )

    response = client.get(
        "/v1/console/costs/summary",
        headers=auth_headers(api_key, environment="production"),
        params={"group_by": "provider", "window_days": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_cost_usd"] == 1.3
    assert body["total_tokens"] == 700
    assert body["run_count"] == 2
    assert body["failed_run_count"] == 1
    assert body["breakdown"] == [
        {
            "group_by": "provider",
            "key": "openai",
            "label": "openai",
            "total_cost_usd": 1.3,
            "total_tokens": 700,
            "run_count": 2,
            "failed_run_count": 1,
            "latest_run_id": prod_run_2,
            "latest_at": body["breakdown"][0]["latest_at"],
            "quality_gate": None,
        }
    ]


def test_cost_anomalies_surface_failed_spend_and_provider_correlation() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="anomaly",
    )
    update_run_and_usage(
        run_id=run_id,
        status="failed",
        cost=2.25,
        total_tokens=800,
        provider="openai",
        model="gpt-4.1",
    )

    response = client.get(
        "/v1/console/costs/anomalies",
        headers=auth_headers(api_key, environment="production"),
    )

    assert response.status_code == 200
    kinds = {item["kind"] for item in response.json()}
    assert "high_cost_failed_run" in kinds
    assert "cost_spike" in kinds
    assert "provider_error_cost_correlation" in kinds


def test_cost_summary_includes_deployment_quality_gate_overlay() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="quality_overlay",
    )
    update_run_and_usage(
        run_id=run_id,
        status="succeeded",
        cost=0.85,
        total_tokens=320,
        provider="openai",
        model="gpt-4.1-mini",
    )
    attach_deployment_quality_gate(
        deployment_id=deployment_id,
        experiment_run_id=401,
        candidate_agent_version_id=1,
        status="passed",
        promotion_allowed=True,
        average_score=1.0,
        min_score=0.8,
    )

    response = client.get(
        "/v1/console/costs/summary",
        headers=auth_headers(api_key, environment="production"),
        params={"group_by": "deployment", "window_days": 30},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["breakdown"][0]["quality_gate"] == {
        "status": "passed",
        "promotion_allowed": True,
        "blocked_reason": None,
        "experiment_run_id": 401,
        "average_score": 1.0,
        "min_score": 0.8,
        "candidate_agent_version_id": 1,
    }


def test_budget_preview_requires_permission_and_returns_dry_run_impact() -> None:
    writer_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
            "policy:update",
        }
    )
    reader_key = create_api_key(scopes={"agent:read"})
    client = TestClient(create_app())
    deployment_id = create_deployment(client, writer_key, environment="production")
    run_id = submit_task(
        client,
        writer_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="budget",
    )
    update_run_and_usage(
        run_id=run_id,
        status="succeeded",
        cost=0.75,
        total_tokens=300,
        provider="openai",
        model="gpt-4.1-mini",
    )

    denied = client.post(
        "/v1/console/costs/budgets/preview",
        headers=auth_headers(reader_key, environment="production"),
        json={
            "threshold_usd": 0.5,
            "scope_type": "deployment",
            "scope_ref": str(deployment_id),
            "reset_window": "monthly",
            "notification_channel": "slack:#ops",
            "action_mode": "require_approval",
        },
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/v1/console/costs/budgets/preview",
        headers=auth_headers(writer_key, environment="production"),
        json={
            "threshold_usd": 0.5,
            "scope_type": "deployment",
            "scope_ref": str(deployment_id),
            "reset_window": "monthly",
            "notification_channel": "slack:#ops",
            "action_mode": "require_approval",
        },
    )

    assert allowed.status_code == 200
    body = allowed.json()
    assert body["current_spend_usd"] == 0.75
    assert body["would_trigger"] is True
    assert body["top_contributors"][0]["key"] == str(deployment_id)
    assert "slack:#ops" in body["notification_preview"]
    assert "require approval" in body["action_preview"]


def test_saved_budget_policy_preview_uses_persisted_channel_and_scope() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
            "policy:update",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="saved_budget",
    )
    update_run_and_usage(
        run_id=run_id,
        status="failed",
        cost=1.9,
        total_tokens=800,
        provider="openai",
        model="gpt-4.1",
    )
    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        channel = NotificationChannel(
            tenant_id=1,
            project_id=1,
            type="webhook",
            target_ref="slack:#ops-finops",
            status="active",
            metadata_json={},
        )
        session.add(channel)
        session.flush()
        policy = CostBudgetPolicy(
            tenant_id=1,
            project_id=1,
            name="prod spend guardrail",
            environment="production",
            scope_type="deployment",
            scope_ref=str(deployment_id),
            threshold_usd=1.0,
            reset_window="monthly",
            channel_id=channel.id,
            action_mode="require_approval",
            status="active",
            metadata_json={},
        )
        session.add(policy)
        session.commit()
        policy_id = policy.id

    response = client.get(
        f"/v1/console/costs/budgets/{policy_id}/preview",
        headers=auth_headers(api_key, environment="production"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scope_ref"] == str(deployment_id)
    assert body["current_spend_usd"] == 1.9
    assert body["would_trigger"] is True
    assert "slack:#ops-finops" in body["notification_preview"]


def test_saved_cost_view_returns_persisted_grouping_and_live_summary() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    production_deployment = create_deployment(client, api_key, environment="production")
    staging_deployment = create_deployment(client, api_key, environment="staging")
    prod_run = submit_task(
        client,
        api_key,
        deployment_id=production_deployment,
        environment="production",
        suffix="saved_view_prod",
    )
    staging_run = submit_task(
        client,
        api_key,
        deployment_id=staging_deployment,
        environment="staging",
        suffix="saved_view_staging",
    )
    update_run_and_usage(
        run_id=prod_run,
        status="failed",
        cost=2.25,
        total_tokens=800,
        provider="openai",
        model="gpt-4.1",
    )
    update_run_and_usage(
        run_id=staging_run,
        status="succeeded",
        cost=4.0,
        total_tokens=1000,
        provider="anthropic",
        model="claude-3-7-sonnet",
    )
    view_id = create_saved_cost_view(
        environment="production",
        name="provider-regressions",
        group_by="provider",
        window_days=30,
        filters={"focus": "failed_runs"},
    )

    response = client.get(
        f"/v1/console/costs/views/{view_id}",
        headers=auth_headers(api_key, environment="production"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item"]["name"] == "provider-regressions"
    assert body["item"]["group_by"] == "provider"
    assert body["item"]["window_days"] == 30
    assert body["item"]["filters"] == {"focus": "failed_runs"}
    assert body["summary"]["total_cost_usd"] == 2.25
    assert body["summary"]["group_by"] == "provider"
    assert body["summary"]["breakdown"][0]["key"] == "openai"
    assert any(item["kind"] == "high_cost_failed_run" for item in body["anomalies"])


def test_budget_enforcement_rejects_deployment_tasks_when_persisted_policy_is_exceeded() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="budget_reject_seed",
    )
    update_run_and_usage(
        run_id=run_id,
        status="succeeded",
        cost=1.4,
        total_tokens=400,
        provider="openai",
        model="gpt-4.1-mini",
    )
    create_budget_policy(
        environment="production",
        scope_type="deployment",
        scope_ref=str(deployment_id),
        threshold_usd=1.0,
        action_mode="reject",
    )

    blocked = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(api_key, environment="production", request_id="req_budget_reject")
        | {"Idempotency-Key": "idem_budget_reject"},
        json={"input": {"message": "should block"}},
    )

    assert blocked.status_code == 403
    body = blocked.json()
    assert body["error_code"] == "cost_budget_exceeded"
    assert body["details"]["deployment_id"] == deployment_id
    assert body["details"]["action_mode"] == "reject"
    assert body["details"]["current_spend_usd"] == 1.4

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session:
        runs = list(session.query(Run).all())
        audits = list(
            session.query(AuditLog)
            .filter(AuditLog.action == "deployment.task.create")
            .order_by(AuditLog.id.asc())
            .all()
        )

    assert len(runs) == 1
    assert audits[-1].result == "denied"
    assert audits[-1].metadata_json["reason"] == "cost_budget_exceeded"
    attempts = list_delivery_attempts()["items"]
    assert len(attempts) == 1
    assert attempts[0]["channel_id"] is not None
    assert attempts[0]["source"] == "cost_budget_policy.reject"
    assert attempts[0]["target_ref"] == "slack:#ops-finops"
    assert "deployment #" in attempts[0]["redacted_payload"]["message"].lower()


def test_budget_enforcement_returns_approval_required_for_require_approval_policy() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="budget_approval_seed",
    )
    update_run_and_usage(
        run_id=run_id,
        status="failed",
        cost=2.2,
        total_tokens=900,
        provider="openai",
        model="gpt-4.1",
    )
    create_budget_policy(
        environment="production",
        scope_type="deployment",
        scope_ref=str(deployment_id),
        threshold_usd=1.0,
        action_mode="require_approval",
    )

    blocked = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(
            api_key,
            environment="production",
            request_id="req_budget_approval",
        )
        | {"Idempotency-Key": "idem_budget_approval"},
        json={"input": {"message": "approval required"}},
    )

    assert blocked.status_code == 403
    body = blocked.json()
    assert body["error_code"] == "approval_required"
    assert body["details"]["action_mode"] == "require_approval"
    assert body["details"]["policy_name"] == "deployment-require_approval-guardrail"
    attempts = list_delivery_attempts()["items"]
    assert len(attempts) == 1
    assert attempts[0]["source"] == "cost_budget_policy.require_approval"
    assert attempts[0]["target_ref"] == "slack:#ops-finops"


def test_budget_enforcement_allows_warn_only_policy() -> None:
    api_key = create_api_key(
        scopes={
            "agent:read",
            "agent:create",
            "agent:deploy",
            "agent:invoke",
            "agent:update",
            "agent:write",
        }
    )
    client = TestClient(create_app())
    deployment_id = create_deployment(client, api_key, environment="production")
    run_id = submit_task(
        client,
        api_key,
        deployment_id=deployment_id,
        environment="production",
        suffix="budget_warn_seed",
    )
    update_run_and_usage(
        run_id=run_id,
        status="succeeded",
        cost=1.8,
        total_tokens=500,
        provider="openai",
        model="gpt-4.1-mini",
    )
    create_budget_policy(
        environment="production",
        scope_type="deployment",
        scope_ref=str(deployment_id),
        threshold_usd=1.0,
        action_mode="warn",
    )

    allowed = client.post(
        f"/v1/deployments/{deployment_id}/tasks",
        headers=auth_headers(api_key, environment="production", request_id="req_budget_warn")
        | {"Idempotency-Key": "idem_budget_warn"},
        json={"input": {"message": "warn only"}},
    )

    assert allowed.status_code == 202
    attempts = list_delivery_attempts()["items"]
    assert len(attempts) == 1
    assert attempts[0]["source"] == "cost_budget_policy.warn"
    assert attempts[0]["target_ref"] == "slack:#ops-finops"
