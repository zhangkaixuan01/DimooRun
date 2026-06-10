import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator, reset_console_identity
from dimoo_run.domain.models import Agent, AgentVersion, Deployment, PublishedSurface, Run
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-identity-{uuid4().hex}.db"
    os.environ["DIMOORUN_BOOTSTRAP_ADMIN_EMAIL"] = "admin@local.dimoorun"
    os.environ["DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD"] = "admin12345"
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["REDIS_URL"] = "memory://identity-test"
    reset_console_identity()
    reset_api_key_authenticator()


def scoped_headers(token: str, request_id: str = "req_identity") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
        "X-Request-Id": request_id,
    }


def login(client: TestClient) -> str:
    response = client.post(
        "/v1/auth/login",
        json={"email": "admin@local.dimoorun", "password": "admin12345"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_role_matrix_preview_reports_diff_and_self_lockout_warning() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token, "req_create_identity_admin"),
        json={
            "email": "identity-admin@local.dimoorun",
            "name": "Identity Admin",
            "password": "identity123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read", "admin:write"],
            "allowed_scopes": [{"tenant_id": 1, "project_id": 1, "environment": "local"}],
        },
    )
    assert created.status_code == 201
    token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "identity-admin@local.dimoorun", "password": "identity123"},
        ).json()["access_token"]
    )
    roles = client.get(
        "/v1/console/identity/role-matrix",
        headers=scoped_headers(admin_token, "req_roles"),
    )
    identity_admin = next(
        item for item in roles.json()["items"] if item["name"] == "identity_admin"
    )

    preview = client.post(
        f"/v1/identity/workflows/roles/{identity_admin['id']}/preview",
        headers=scoped_headers(token, "req_preview"),
        json={"permissions": ["admin:read"]},
    )

    assert preview.status_code == 200
    body = preview.json()["item"]
    assert "identity:role:write" in body["change"]["removed"]
    assert body["affected_operators"]
    assert any(warning["code"] == "self_lockout_risk" for warning in body["warnings"])


def test_role_matrix_apply_requires_audit_reason_and_blocks_self_lockout() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token, "req_create_identity_admin"),
        json={
            "email": "identity-admin-apply@local.dimoorun",
            "name": "Identity Admin Apply",
            "password": "identity123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read", "admin:write"],
            "allowed_scopes": [{"tenant_id": 1, "project_id": 1, "environment": "local"}],
        },
    )
    assert created.status_code == 201
    token = str(
        client.post(
            "/v1/auth/login",
            json={
                "email": "identity-admin-apply@local.dimoorun",
                "password": "identity123",
            },
        ).json()["access_token"]
    )
    roles = client.get(
        "/v1/console/identity/role-matrix",
        headers=scoped_headers(admin_token, "req_roles"),
    )
    identity_admin = next(
        item for item in roles.json()["items"] if item["name"] == "identity_admin"
    )

    missing_reason = client.post(
        f"/v1/identity/workflows/roles/{identity_admin['id']}/apply",
        headers=scoped_headers(token, "req_apply_no_reason"),
        json={"permissions": ["admin:read"]},
    )
    blocked = client.post(
        f"/v1/identity/workflows/roles/{identity_admin['id']}/apply",
        headers={
            **scoped_headers(token, "req_apply_blocked"),
            "X-Audit-Reason": "test role reduction",
        },
        json={"permissions": ["admin:read"]},
    )

    assert missing_reason.status_code == 400
    assert missing_reason.json()["error_code"] == "audit_reason_required"
    assert blocked.status_code == 409
    assert blocked.json()["error_code"] == "self_lockout_blocked"


def test_operator_access_detail_exposes_sessions_and_recent_audit() -> None:
    client = TestClient(create_app())
    token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(token, "req_create_operator"),
        json={
            "email": "reviewer@local.dimoorun",
            "name": "Reviewer",
            "password": "reviewer123",
            "roles": ["runtime_operator"],
            "permissions": ["admin:read"],
            "allowed_scopes": [{"tenant_id": 1, "project_id": 1, "environment": "local"}],
        },
    )
    assert created.status_code == 201
    operator_id = created.json()["item"]["id"]
    login_response = client.post(
        "/v1/auth/login",
        headers={"User-Agent": "Identity Workflow Browser"},
        json={"email": "reviewer@local.dimoorun", "password": "reviewer123"},
    )
    assert login_response.status_code == 200

    detail = client.get(
        f"/v1/console/identity/operators/{operator_id}",
        headers=scoped_headers(token, "req_operator_detail"),
    )

    assert detail.status_code == 200
    item = detail.json()["item"]
    assert item["email"] == "reviewer@local.dimoorun"
    assert item["active_sessions"]
    assert item["active_sessions"][0]["user_agent"] == "Identity Workflow Browser"
    assert item["disable_impact"]["active_session_count"] >= 1


def test_revoke_self_session_invalidates_token() -> None:
    client = TestClient(create_app())
    token = login(client)

    revoked = client.post(
        "/v1/identity/workflows/sessions/revoke-self",
        headers=scoped_headers(token, "req_revoke_self"),
        json={"token": token},
    )
    after = client.get("/v1/auth/me", headers=scoped_headers(token, "req_after_revoke"))

    assert revoked.status_code == 200
    assert after.status_code == 401


def test_service_account_detail_rotation_and_force_expire() -> None:
    client = TestClient(create_app())
    token = login(client)
    service_account = client.post(
        "/v1/identity/service-accounts",
        headers=scoped_headers(token, "req_sa_create"),
        json={
            "name": "workflow-sa",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read", "agent:deploy"],
        },
    )
    assert service_account.status_code == 201
    service_account_id = service_account.json()["item"]["id"]
    key = client.post(
        f"/v1/identity/service-accounts/{service_account_id}/api-keys",
        headers=scoped_headers(token, "req_key_create"),
        json={"name": "workflow-key", "scopes": ["agent:read"]},
    )
    assert key.status_code == 201
    key_id = key.json()["item"]["id"]

    database_url = os.environ["DATABASE_URL"]
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        Base.metadata.create_all(session.get_bind())
        agent = Agent(tenant_id=1, project_id=1, name="identity-agent", status="active")
        session.add(agent)
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version="1.0.0",
            package_uri="file://identity-agent",
            framework="langgraph",
            adapter="langgraph",
            entrypoint="agent:app",
            capabilities_json={},
            manifest_json={},
            status="ready",
        )
        session.add(version)
        session.flush()
        deployment = Deployment(
            tenant_id=1,
            project_id=1,
            agent_id=agent.id,
            agent_version_id=version.id,
            environment="local",
            desired_status="active",
            runtime_status="ready",
            replicas=1,
            config_json={},
        )
        session.add(deployment)
        session.flush()
        session.add(
            Run(
                tenant_id=1,
                project_id=1,
                service_account_id=service_account_id,
                agent_id=agent.id,
                agent_version_id=version.id,
                deployment_id=deployment.id,
                status="pending",
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            )
        )
        session.add(
            PublishedSurface(
                tenant_id=1,
                project_id=1,
                deployment_id=deployment.id,
                type="http",
                metadata_json={"name": "identity-surface"},
                status="active",
                created_by="test",
                updated_by="test",
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            )
        )
        session.commit()

    detail = client.get(
        f"/v1/console/identity/service-accounts/{service_account_id}",
        headers=scoped_headers(token, "req_sa_detail"),
    )
    assert detail.status_code == 200
    assert detail.json()["item"]["dependent_deployments"]

    rotated = client.post(
        f"/v1/identity/workflows/service-accounts/{service_account_id}/api-keys/{key_id}/rotate",
        headers={
            **scoped_headers(token, "req_key_rotate"),
            "X-Audit-Reason": "rotate service credential",
        },
        json={"name": "workflow-key-rotated", "scopes": ["agent:read", "agent:deploy"]},
    )
    assert rotated.status_code == 200
    assert rotated.json()["plain_key"].startswith("dr_")
    rotated_key_id = rotated.json()["item"]["id"]

    expired = client.post(
        f"/v1/identity/workflows/service-accounts/{service_account_id}/api-keys/{rotated_key_id}/force-expire",
        headers={
            **scoped_headers(token, "req_key_expire"),
            "X-Audit-Reason": "expire rotated credential",
        },
    )
    rejected = client.get(
        "/v1/agents",
        headers={
            "Authorization": f"Bearer {rotated.json()['plain_key']}",
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
            "X-Request-Id": "req_expired_key",
        },
    )

    assert expired.status_code == 200
    assert expired.json()["item"]["status"] == "disabled"
    assert rejected.status_code == 401
