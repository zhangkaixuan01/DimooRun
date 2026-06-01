import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_console_identity
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import ConsolePermission, ConsoleRole, ConsoleRolePermission
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import delete, select


def setup_function() -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-console-{uuid4().hex}.db"
    os.environ["DIMOORUN_BOOTSTRAP_ADMIN_EMAIL"] = "admin@local.dimoorun"
    os.environ["DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD"] = "admin12345"
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["REDIS_URL"] = "memory://console-test"
    os.environ["DIMOORUN_CONSOLE_ACCESS_TOKEN_TTL_SECONDS"] = "43200"
    reset_console_identity()


def scoped_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
        "X-Request-Id": "req_auth",
    }


def login(client: TestClient) -> str:
    response = client.post(
        "/v1/auth/login",
        json={"email": "admin@local.dimoorun", "password": "admin12345"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_console_login_me_logout_flow() -> None:
    client = TestClient(create_app())
    token = login(client)

    me = client.get("/v1/auth/me", headers=scoped_headers(token))
    assert me.status_code == 200
    assert me.json()["operator"]["email"] == "admin@local.dimoorun"
    assert me.json()["operator"]["allowed_scopes"] == [
        {
            "tenant_id": 1,
            "tenant_name": "Default Tenant",
            "project_id": 1,
            "project_name": "Default Project",
            "environment": "local",
            "environment_name": "local",
        }
    ]

    logout = client.post("/v1/auth/logout", headers=scoped_headers(token))
    assert logout.status_code == 200

    after_logout = client.get("/v1/auth/me", headers=scoped_headers(token))
    assert after_logout.status_code == 401


def test_admin_collection_requires_console_auth() -> None:
    client = TestClient(create_app())

    denied = client.get(
        "/v1/policies",
        headers={
            "X-Tenant-Id": "1",
            "X-Project-Id": "1",
            "X-Request-Id": "req_auth",
        },
    )
    token = login(client)
    allowed = client.get("/v1/policies", headers=scoped_headers(token))

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_operator_management_and_password_reset() -> None:
    client = TestClient(create_app())
    token = login(client)

    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(token),
        json={
            "email": "ops@local.dimoorun",
            "name": "Ops Operator",
            "password": "operator123",
            "roles": ["runtime_operator"],
            "permissions": ["agent:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    assert created.status_code == 201
    operator_id = created.json()["item"]["id"]
    assert created.json()["item"]["allowed_scopes"] == [
        {
            "tenant_id": 1,
            "tenant_name": "Default Tenant",
            "project_id": 1,
            "project_name": "Default Project",
            "environment": "local",
            "environment_name": "local",
        }
    ]

    listed = client.get("/v1/identity/operators", headers=scoped_headers(token))
    assert listed.status_code == 200
    assert any(item["email"] == "ops@local.dimoorun" for item in listed.json()["items"])

    updated = client.patch(
        f"/v1/identity/operators/{operator_id}",
        headers=scoped_headers(token),
        json={"status": "disabled"},
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "disabled"

    reset = client.post(
        f"/v1/identity/operators/{operator_id}/reset-password",
        headers=scoped_headers(token),
        json={"new_password": "operator456"},
    )
    assert reset.status_code == 200


def test_password_reset_revokes_existing_operator_sessions() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "reset@local.dimoorun",
            "name": "Reset Operator",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    operator_id = created.json()["item"]["id"]
    operator_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "reset@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )

    reset = client.post(
        f"/v1/identity/operators/{operator_id}/reset-password",
        headers=scoped_headers(admin_token),
        json={"new_password": "operator456"},
    )
    after_reset = client.get("/v1/auth/me", headers=scoped_headers(operator_token))

    assert reset.status_code == 200
    assert after_reset.status_code == 401


def test_revoke_operator_sessions_endpoint_invalidates_existing_sessions() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "revoke@local.dimoorun",
            "name": "Revoke Operator",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    operator_id = created.json()["item"]["id"]
    operator_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "revoke@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )

    revoked = client.post(
        f"/v1/identity/operators/{operator_id}/revoke-sessions",
        headers=scoped_headers(admin_token),
    )
    after_revoke = client.get("/v1/auth/me", headers=scoped_headers(operator_token))

    assert revoked.status_code == 200
    assert after_revoke.status_code == 401


def test_list_operator_sessions_hides_token_hash_and_reports_status() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "sessions@local.dimoorun",
            "name": "Sessions Operator",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    operator_id = created.json()["item"]["id"]
    client.post(
        "/v1/auth/login",
        headers={"User-Agent": "DimooRun Test Browser"},
        json={"email": "sessions@local.dimoorun", "password": "operator123"},
    )

    listed = client.get(
        f"/v1/identity/operators/{operator_id}/sessions",
        headers=scoped_headers(admin_token),
    )

    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] == 1
    session = body["items"][0]
    assert session["operator_id"] == operator_id
    assert session["status"] == "active"
    assert session["last_used_at"]
    assert session["expires_at"]
    assert session["revoked_at"] is None
    assert session["revoke_reason"] is None
    assert "token_hash" not in session
    assert "DimooRun Test Browser" in session["user_agent"]


def test_delete_operator_soft_deletes_and_revokes_sessions() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "delete@local.dimoorun",
            "name": "Delete Operator",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    operator_id = created.json()["item"]["id"]
    operator_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "delete@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )

    deleted = client.delete(
        f"/v1/identity/operators/{operator_id}",
        headers=scoped_headers(admin_token),
    )
    listed = client.get("/v1/identity/operators", headers=scoped_headers(admin_token))
    after_delete = client.get("/v1/auth/me", headers=scoped_headers(operator_token))

    assert deleted.status_code == 200
    assert deleted.json()["item"]["status"] == "deleted"
    assert all(item["id"] != operator_id for item in listed.json()["items"])
    assert after_delete.status_code == 401


def test_disabled_operator_session_is_denied() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "disabled@local.dimoorun",
            "name": "Disabled Operator",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    operator_id = created.json()["item"]["id"]
    operator_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "disabled@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )

    disabled = client.patch(
        f"/v1/identity/operators/{operator_id}",
        headers=scoped_headers(admin_token),
        json={"status": "disabled"},
    )
    after_disabled = client.get("/v1/auth/me", headers=scoped_headers(operator_token))

    assert disabled.status_code == 200
    assert after_disabled.status_code == 401


def test_operator_session_is_restricted_to_allowed_scope() -> None:
    client = TestClient(create_app())
    admin_token = login(client)

    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "scoped@local.dimoorun",
            "name": "Scoped Operator",
            "password": "operator123",
            "roles": ["runtime_operator"],
            "permissions": ["admin:read"],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    assert created.status_code == 201

    scoped_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "scoped@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )
    denied = client.get(
        "/v1/policies",
            headers={
                "Authorization": f"Bearer {scoped_token}",
                "X-Tenant-Id": "999",
                "X-Project-Id": "1",
                "X-Environment": "local",
            },
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["error_code"] == "scope_not_allowed"


def test_builtin_identity_admin_permissions_are_persisted_for_existing_bootstrap() -> None:
    client = TestClient(create_app())
    admin_token = login(client)
    created = client.post(
        "/v1/identity/operators",
        headers=scoped_headers(admin_token),
        json={
            "email": "identity-admin@local.dimoorun",
            "name": "Identity Admin",
            "password": "operator123",
            "roles": ["identity_admin"],
            "permissions": [],
            "allowed_scopes": [
                {"tenant_id": 1, "project_id": 1, "environment": "local"}
            ],
        },
    )
    assert created.status_code == 201

    session_factory = create_session_factory(Settings.from_env().database.url)
    with session_factory() as session:
        identity_admin = session.scalar(
            select(ConsoleRole).where(ConsoleRole.name == "identity_admin")
        )
        assert identity_admin is not None
        permission_ids = list(
            session.scalars(
                select(ConsolePermission.id).where(
                    ConsolePermission.code.in_(
                        ["identity:service-account:write", "identity:api-key:write"]
                    )
                )
            )
        )
        session.execute(
            delete(ConsoleRolePermission).where(
                ConsoleRolePermission.role_id == identity_admin.id,
                ConsoleRolePermission.permission_id.in_(permission_ids),
            )
        )
        session.commit()

    operator_token = str(
        client.post(
            "/v1/auth/login",
            json={"email": "identity-admin@local.dimoorun", "password": "operator123"},
        ).json()["access_token"]
    )
    created_service_account = client.post(
        "/v1/identity/service-accounts",
        headers=scoped_headers(operator_token),
        json={
            "name": "identity-admin-sa",
            "tenant_id": 1,
            "project_id": 1,
            "permissions": ["agent:read"],
        },
    )

    assert created_service_account.status_code == 201
