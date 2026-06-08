import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.domain.models import PublishedSurfaceEvidenceBundle
from dimoo_run.gateway.route_tester import reset_gateway_workflows
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-published-{uuid4().hex}.db"
    reset_api_key_authenticator()
    reset_native_runtime()


def admin_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": "req_published",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
    }


def _persisted_evidence_bundle(bundle_id: str) -> PublishedSurfaceEvidenceBundle | None:
    database_url = os.environ["DATABASE_URL"]
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        return session.scalar(
            select(PublishedSurfaceEvidenceBundle).where(
                PublishedSurfaceEvidenceBundle.bundle_id == bundle_id
            )
        )


def valid_surface_payload() -> dict[str, object]:
    return {
        "surface": {
            "name": "support-public-api",
            "deployment_id": 10,
            "environment": "local",
            "auth_mode": "api_key",
            "route_path": "/support/triage",
            "cors_policy": {"allowed_origins": ["https://app.example.com"]},
            "rate_limit_policy": {"requests_per_minute": 120},
            "policy_enforced": True,
        }
    }


def test_publish_validation_checks_route_binding_policy_and_guardrails() -> None:
    client = TestClient(create_app())

    valid = client.post(
        "/v1/published-surfaces/validate",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    invalid = client.post(
        "/v1/published-surfaces/validate",
        headers=admin_headers(),
        json={
            "surface": {
                "name": "broken-public-api",
                "deployment_id": None,
                "environment": "prod",
                "auth_mode": "none",
                "route_path": "support",
                "cors_policy": {"allowed_origins": ["*"]},
                "rate_limit_policy": {},
                "policy_enforced": False,
            }
        },
    )

    assert valid.status_code == 200
    valid_body = valid.json()
    assert valid_body["status"] == "valid"
    assert valid_body["can_publish"] is True
    assert valid_body["checks"]["route_path"]["valid"] is True
    assert valid_body["checks"]["deployment_binding"]["valid"] is True
    assert valid_body["checks"]["cors_policy"]["valid"] is True
    assert valid_body["checks"]["rate_limit_policy"]["valid"] is True
    assert valid_body["checks"]["policy_engine"]["valid"] is True
    assert valid_body["audit"]["action"] == "published_surface.validate"
    assert invalid.status_code == 200
    invalid_body = invalid.json()
    assert invalid_body["status"] == "invalid"
    assert invalid_body["can_publish"] is False
    assert "route_path_invalid" in invalid_body["blocked_reasons"]
    assert "auth_mode_unsafe" in invalid_body["blocked_reasons"]
    assert "deployment_binding_missing" in invalid_body["blocked_reasons"]
    assert "cors_wildcard_origin" in invalid_body["blocked_reasons"]
    assert "rate_limit_missing" in invalid_body["blocked_reasons"]
    assert "policy_engine_not_enforced" in invalid_body["blocked_reasons"]


def test_publish_validation_blocks_malformed_numeric_policy_fields_without_server_error() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["deployment_id"] = "ten"
    surface["rate_limit_policy"] = {"requests_per_minute": "fast"}

    response = client.post(
        "/v1/published-surfaces/validate",
        headers=admin_headers(),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["can_publish"] is False
    assert body["checks"]["deployment_binding"]["valid"] is False
    assert body["checks"]["rate_limit_policy"]["valid"] is False
    assert "deployment_binding_missing" in body["blocked_reasons"]
    assert "rate_limit_missing" in body["blocked_reasons"]


def test_publish_validation_blocks_fractional_numeric_policy_fields() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["deployment_id"] = 10.5
    surface["rate_limit_policy"] = {"requests_per_minute": 120.5}

    response = client.post(
        "/v1/published-surfaces/validate",
        headers=admin_headers(),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["can_publish"] is False
    assert body["checks"]["deployment_binding"]["valid"] is False
    assert body["checks"]["rate_limit_policy"]["valid"] is False
    assert "deployment_binding_missing" in body["blocked_reasons"]
    assert "rate_limit_missing" in body["blocked_reasons"]


def test_publish_validation_blocks_leading_zero_numeric_policy_fields() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["deployment_id"] = "010"
    surface["rate_limit_policy"] = {"requests_per_minute": "0120"}

    response = client.post(
        "/v1/published-surfaces/validate",
        headers=admin_headers(),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "invalid"
    assert body["can_publish"] is False
    assert body["checks"]["deployment_binding"]["valid"] is False
    assert body["checks"]["rate_limit_policy"]["valid"] is False
    assert "deployment_binding_missing" in body["blocked_reasons"]
    assert "rate_limit_missing" in body["blocked_reasons"]


def test_publish_validation_blocks_invalid_environment_scope() -> None:
    client = TestClient(create_app())

    for environment in ["", " production", "qa"]:
        payload = valid_surface_payload()
        surface = payload["surface"]
        assert isinstance(surface, dict)
        surface["environment"] = environment

        response = client.post(
            "/v1/published-surfaces/validate",
            headers=admin_headers(),
            json=payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "invalid"
        assert body["can_publish"] is False
        assert body["checks"]["environment_scope"]["valid"] is False
        assert body["checks"]["environment_scope"]["environment"] == environment
        assert "environment_scope_invalid" in body["blocked_reasons"]


def test_publish_validation_blocks_unsafe_route_path_shapes() -> None:
    client = TestClient(create_app())

    for route_path in ["/support/../admin", "/support/triage?debug=true", "/support/triage#debug"]:
        payload = valid_surface_payload()
        surface = payload["surface"]
        assert isinstance(surface, dict)
        surface["route_path"] = route_path

        response = client.post(
            "/v1/published-surfaces/validate",
            headers=admin_headers(),
            json=payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "invalid"
        assert body["can_publish"] is False
        assert body["checks"]["route_path"]["valid"] is False
        assert "route_path_invalid" in body["blocked_reasons"]


def test_publish_validation_blocks_malformed_cors_allowed_origins() -> None:
    client = TestClient(create_app())

    for allowed_origins in ["https://app.example.com", ["https://app.example.com", " "], []]:
        payload = valid_surface_payload()
        surface = payload["surface"]
        assert isinstance(surface, dict)
        surface["cors_policy"] = {"allowed_origins": allowed_origins}

        response = client.post(
            "/v1/published-surfaces/validate",
            headers=admin_headers(),
            json=payload,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "invalid"
        assert body["can_publish"] is False
        assert body["checks"]["cors_policy"]["valid"] is False
        assert "cors_wildcard_origin" in body["blocked_reasons"]


def test_publish_blocks_malformed_surface_id_without_server_error() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["surface_id"] = "public"

    response = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["can_publish"] is False
    assert body["surface"] is None
    assert body["rollout"] is None
    assert "surface_id_invalid" in body["blocked_reasons"]
    assert body["audit"]["resource_id"] is None
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-publish-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.publish",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.publish.blocked"
    assert body["audit"]["action"] == "published_surface.publish.blocked"
    assert body["impact_preview"]["blocked_reasons"] == ["surface_id_invalid"]


def test_publish_validation_failure_does_not_append_rollout_history() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["policy_enforced"] = False

    response = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["can_publish"] is False
    assert body["surface"] is None
    assert body["rollout"] is None
    assert "policy_engine_not_enforced" in body["blocked_reasons"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-publish-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.publish",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.publish.blocked"
    assert body["audit"] == {
        "action": "published_surface.publish.blocked",
        "resource_type": "published_surface",
        "resource_id": None,
        "request_id": "req_published",
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert body["impact_preview"]["blocked_reasons"] == body["blocked_reasons"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_route_test_returns_gateway_decisions_runtime_shape_and_request_log() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live", "x-user": "operator"},
            "body": {"ticket_id": "INC-900", "secret": "redact-me"},
        },
    )

    assert route_test.status_code == 200
    body = route_test.json()
    assert body["status"] == "matched"
    assert body["matched_deployment"]["deployment_id"] == 10
    assert body["auth_decision"]["result"] == "allow"
    assert body["policy_decision"]["result"] == "allow"
    assert body["expected_runtime_task"]["deployment_id"] == 10
    assert body["expected_runtime_task"]["task_shape"] == "deployment.invoke"
    assert body["blocked_reasons"] == []
    assert body["request_log"]["status"] == 200
    assert body["request_log"]["trace_id"].startswith("trace_")
    metadata = body["request_log"]["redacted_request_metadata"]
    assert metadata["headers"]["authorization"] == "[REDACTED]"
    assert body["audit"]["action"] == "ingress_route.test"


def test_route_test_uses_published_surface_deployment_binding() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["deployment_id"] = 44
    surface["environment"] = "staging"
    surface["auth_mode"] = "jwt"

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert publish.json()["surface"]["deployment_id"] == 44
    assert route_test.status_code == 200
    body = route_test.json()
    assert body["matched_deployment"]["deployment_id"] == 44
    assert body["matched_deployment"]["environment"] == "staging"
    assert body["auth_decision"]["mode"] == "jwt"
    assert body["expected_runtime_task"]["deployment_id"] == 44
    assert body["request_log"]["deployment_id"] == 44
    assert body["request_log"]["environment"] == "staging"
    assert body["request_log"]["auth_mode"] == "jwt"
    assert detail.status_code == 200
    assert detail.json()["request_logs"][0]["deployment_id"] == 44
    assert detail.json()["request_logs"][0]["environment"] == "staging"
    assert detail.json()["request_logs"][0]["auth_mode"] == "jwt"
    publish_entry = detail.json()["rollout_history"][0]
    assert publish_entry["operation"] == "publish"
    assert publish_entry["permission_summary"] == {
        "required_permission": "published_surface.publish",
        "actor_permission": "allowed",
    }
    assert publish_entry["policy_decision"] == {
        "result": "allow",
        "policy_id": "published-surface-publish-controls",
    }
    assert publish_entry["audit_preview"]["action"] == "published_surface.publish"
    assert publish_entry["impact_preview"]["affected_resources"] == [
        "published_surface:501",
        "deployment:44",
        "ingress_route:701",
    ]
    assert publish_entry["impact_preview"]["expected_runtime_effect"] == (
        "external_traffic_exposed"
    )
    assert publish_entry["audit_scope"] == {
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }


def test_live_ingress_request_uses_published_surface_and_writes_request_log() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["deployment_id"] = 44
    surface["environment"] = "staging"
    surface["auth_mode"] = "jwt"

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={
            "Authorization": "Bearer runtime-token",
            "X-Request-Id": "req_live_ingress",
            "X-Client-Ref": "support-desk",
        },
        json={"ticket_id": "INC-901", "secret": "redact-me"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert ingress.status_code == 200
    ingress_body = ingress.json()
    assert ingress_body["status"] == "accepted"
    assert ingress_body["trace_id"].startswith("trace_")
    assert ingress_body["matched_deployment"] == {
        "deployment_id": 44,
        "environment": "staging",
        "surface_id": 501,
        "route_id": 701,
    }
    assert ingress_body["runtime_task"] == {
        "deployment_id": 44,
        "task_shape": "deployment.invoke",
        "method": "POST",
        "path": "/support/triage",
    }
    assert ingress.headers["X-Request-Id"] == "req_live_ingress"
    assert ingress.headers["X-DimooRun-Trace-Id"] == ingress_body["trace_id"]
    assert detail.status_code == 200
    request_log = detail.json()["request_logs"][0]
    assert request_log["id"] == ingress_body["request_log_id"]
    assert request_log["ingress_source"] == "live_http"
    assert request_log["deployment_id"] == 44
    assert request_log["environment"] == "staging"
    assert request_log["auth_mode"] == "jwt"
    assert request_log["path"] == "/support/triage"
    assert request_log["method"] == "POST"
    assert request_log["redacted_request_metadata"]["headers"]["authorization"] == "[REDACTED]"
    assert sorted(request_log["redacted_request_metadata"]["body_keys"]) == [
        "secret",
        "ticket_id",
    ]


def test_published_surface_binding_survives_gateway_workflow_reset() -> None:
    client = TestClient(create_app())

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    reset_gateway_workflows()
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={
            "Authorization": "Bearer runtime-token",
            "X-Request-Id": "req_durable_surface_binding",
        },
        json={"ticket_id": "INC-930"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert ingress.status_code == 200
    assert ingress.json()["matched_deployment"]["surface_id"] == 501
    assert ingress.json()["runtime_task"]["path"] == "/support/triage"
    assert detail.status_code == 200
    assert detail.json()["surface"]["published_at"] == publish.json()["surface"]["published_at"]
    assert detail.json()["surface"]["route_path"] == "/support/triage"


def test_live_ingress_echoes_allowed_origin_cors_headers() -> None:
    client = TestClient(create_app())

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    allowed = client.post(
        "/v1/ingress/support/triage",
        headers={
            "Authorization": "Bearer runtime-token",
            "Origin": "https://app.example.com",
            "X-Request-Id": "req_allowed_origin",
        },
        json={"ticket_id": "INC-904"},
    )
    denied = client.post(
        "/v1/ingress/support/triage",
        headers={
            "Authorization": "Bearer runtime-token",
            "Origin": "https://evil.example.com",
            "X-Request-Id": "req_denied_origin",
        },
        json={"ticket_id": "INC-905"},
    )

    assert publish.status_code == 200
    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert allowed.headers["Vary"] == "Origin"
    assert allowed.json()["cors"] == {
        "origin": "https://app.example.com",
        "allowed": True,
    }
    assert denied.status_code == 403
    assert denied.json()["blocked_reasons"] == ["cors_origin_not_allowed"]
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_live_ingress_handles_cors_preflight_for_published_surface() -> None:
    client = TestClient(create_app())

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    allowed = client.options(
        "/v1/ingress/support/triage",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
            "X-Request-Id": "req_preflight_allowed",
        },
    )
    denied = client.options(
        "/v1/ingress/support/triage",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "X-Request-Id": "req_preflight_denied",
        },
    )

    assert publish.status_code == 200
    assert allowed.status_code == 204
    assert allowed.content == b""
    assert allowed.headers["X-Request-Id"] == "req_preflight_allowed"
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://app.example.com"
    assert allowed.headers["Access-Control-Allow-Methods"] == "GET, POST, PUT, PATCH, DELETE"
    assert allowed.headers["Access-Control-Allow-Headers"] == "authorization, content-type"
    assert allowed.headers["Vary"] == "Origin"
    assert denied.status_code == 403
    assert denied.headers["X-Request-Id"] == "req_preflight_denied"
    assert denied.json()["blocked_reasons"] == ["cors_origin_not_allowed"]
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_live_ingress_generates_request_id_when_client_omits_header() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token"},
        json={"ticket_id": "INC-902"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert ingress.status_code == 200
    ingress_body = ingress.json()
    assert isinstance(ingress_body["request_id"], str)
    assert ingress_body["request_id"].startswith("req_live_")
    assert ingress.headers["X-Request-Id"] == ingress_body["request_id"]
    assert ingress.headers["X-DimooRun-Trace-Id"] == ingress_body["trace_id"]
    assert detail.status_code == 200
    request_log = detail.json()["request_logs"][0]
    assert request_log["request_id"] == ingress_body["request_id"]
    assert request_log["evidence_bundle"]["request_id"] == ingress_body["request_id"]


def test_live_ingress_blocked_response_exposes_request_id_header() -> None:
    client = TestClient(create_app())

    ingress = client.post(
        "/v1/ingress/support/missing",
        headers={"X-Request-Id": "req_missing_ingress"},
        json={"ticket_id": "INC-903"},
    )

    assert ingress.status_code == 404
    body = ingress.json()
    assert body["request_id"] == "req_missing_ingress"
    assert body["blocked_reasons"] == ["route_not_found"]
    assert ingress.headers["X-Request-Id"] == "req_missing_ingress"
    assert "X-DimooRun-Trace-Id" not in ingress.headers


def test_request_logs_and_rollouts_include_evidence_bundle_references() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live", "x-user": "operator"},
            "body": {"ticket_id": "INC-902", "secret": "redact-me"},
        },
    )
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80, "candidate": 20},
            "audit_reason": "canary published surface",
        },
    )
    log_id = route_test.json()["request_log"]["id"]
    drilldown = client.get(
        f"/v1/console/published-surfaces/501/request-logs/{log_id}",
        headers=admin_headers(),
    )

    assert route_test.status_code == 200
    route_bundle = route_test.json()["request_log"]["evidence_bundle"]
    assert route_bundle["bundle_id"] == f"published-surface-request-log-501-{log_id}"
    assert route_bundle["resource_type"] == "published_surface_request_log"
    assert route_bundle["surface_id"] == 501
    assert route_bundle["request_log_id"] == log_id
    assert route_bundle["trace_id"] == route_test.json()["request_log"]["trace_id"]
    assert route_bundle["policy_decision"] == route_test.json()["policy_decision"]
    assert route_bundle["traffic_control"] == route_test.json()["traffic_control"]
    assert route_bundle["redaction"] == {
        "headers": ["authorization"],
        "body": "keys_only",
    }
    assert drilldown.status_code == 200
    assert drilldown.json()["request_log"]["evidence_bundle"] == route_bundle

    assert rollout.status_code == 200
    rollout_entry = rollout.json()["rollout"]
    rollout_bundle = rollout_entry["evidence_bundle"]
    assert rollout_bundle["bundle_id"] == f"published-surface-rollout-501-{rollout_entry['id']}"
    assert rollout_bundle["resource_type"] == "published_surface_rollout"
    assert rollout_bundle["surface_id"] == 501
    assert rollout_bundle["rollout_id"] == rollout_entry["id"]
    assert rollout_bundle["operation"] == "traffic_split"
    assert rollout_bundle["audit_scope"] == {
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert rollout_bundle["policy_decision"] == rollout_entry["policy_decision"]
    assert rollout_bundle["impact_preview"] == rollout_entry["impact_preview"]


def test_request_logs_survive_gateway_workflow_reset() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-904", "secret": "redact-me"},
        },
    )
    log = route_test.json()["request_log"]
    reset_gateway_workflows()
    detail_after_reset = client.get(
        "/v1/console/published-surfaces/501",
        headers=admin_headers(),
    )
    drilldown_after_reset = client.get(
        f"/v1/console/published-surfaces/501/request-logs/{log['id']}",
        headers=admin_headers(),
    )

    assert route_test.status_code == 200
    assert detail_after_reset.status_code == 200
    persisted_log = detail_after_reset.json()["request_logs"][0]
    assert persisted_log["id"] == log["id"]
    assert persisted_log["surface_id"] == 501
    assert persisted_log["status"] == 200
    assert persisted_log["trace_id"] == log["trace_id"]
    assert persisted_log["redacted_request_metadata"] == log["redacted_request_metadata"]
    assert persisted_log["evidence_bundle"] == log["evidence_bundle"]
    assert drilldown_after_reset.status_code == 200
    assert drilldown_after_reset.json()["request_log"] == persisted_log


def test_rollout_history_survives_gateway_workflow_reset() -> None:
    client = TestClient(create_app())

    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 75, "candidate": 25},
            "audit_reason": "canary published surface with durable rollout history",
        },
    )
    rollout_entry = rollout.json()["rollout"]
    reset_gateway_workflows()
    detail_after_reset = client.get(
        "/v1/console/published-surfaces/501",
        headers=admin_headers(),
    )

    assert rollout.status_code == 200
    assert detail_after_reset.status_code == 200
    persisted_rollout = detail_after_reset.json()["rollout_history"][0]
    assert persisted_rollout == rollout_entry
    assert persisted_rollout["evidence_bundle"]["bundle_id"] == (
        f"published-surface-rollout-501-{rollout_entry['id']}"
    )


def test_console_exports_redacted_evidence_bundles_by_bundle_id() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-904", "secret": "redact-me"},
        },
    )
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 90, "candidate": 10},
            "audit_reason": "export evidence for review",
        },
    )

    request_bundle_id = route_test.json()["request_log"]["evidence_bundle"]["bundle_id"]
    rollout_bundle_id = rollout.json()["rollout"]["evidence_bundle"]["bundle_id"]
    request_export = client.get(
        f"/v1/console/published-surfaces/501/evidence-bundles/{request_bundle_id}",
        headers=admin_headers(),
    )
    rollout_export = client.get(
        f"/v1/console/published-surfaces/501/evidence-bundles/{rollout_bundle_id}",
        headers=admin_headers(),
    )
    cross_surface = client.get(
        f"/v1/console/published-surfaces/502/evidence-bundles/{request_bundle_id}",
        headers=admin_headers(),
    )

    assert request_export.status_code == 200
    request_body = request_export.json()
    assert request_body["export_format"] == "redacted_json"
    assert request_body["evidence_bundle"]["bundle_id"] == request_bundle_id
    assert request_body["evidence_bundle"]["redaction"] == {
        "headers": ["authorization"],
        "body": "keys_only",
    }
    assert request_body["redacted_payload"]["request_metadata"]["headers"]["authorization"] == (
        "[REDACTED]"
    )
    assert request_body["redacted_payload"]["request_metadata"]["body_keys"] == [
        "secret",
        "ticket_id",
    ]
    assert "redact-me" not in str(request_body)

    assert rollout_export.status_code == 200
    rollout_body = rollout_export.json()
    assert rollout_body["export_format"] == "redacted_json"
    assert rollout_body["evidence_bundle"]["bundle_id"] == rollout_bundle_id
    assert rollout_body["redacted_payload"]["operation"] == "traffic_split"
    assert rollout_body["redacted_payload"]["traffic_split"] == {"stable": 90, "candidate": 10}
    assert rollout_body["redacted_payload"]["audit_scope"] == {
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }

    assert cross_surface.status_code == 404
    assert cross_surface.json()["error_code"] == "evidence_bundle_not_found"


def test_evidence_bundle_exports_are_written_to_audit_log() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-917", "secret": "redact-me"},
        },
    )
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 70, "candidate": 30},
            "audit_reason": "export evidence with immutable audit trail",
        },
    )
    request_bundle_id = route_test.json()["request_log"]["evidence_bundle"]["bundle_id"]
    rollout_bundle_id = rollout.json()["rollout"]["evidence_bundle"]["bundle_id"]

    request_export = client.get(
        f"/v1/console/published-surfaces/501/evidence-bundles/{request_bundle_id}",
        headers={**admin_headers(), "X-Request-Id": "req_export_request_bundle"},
    )
    rollout_export = client.get(
        f"/v1/console/published-surfaces/501/evidence-bundles/{rollout_bundle_id}",
        headers={**admin_headers(), "X-Request-Id": "req_export_rollout_bundle"},
    )
    audit_logs = client.get("/v1/audit-logs", headers=admin_headers())

    assert request_export.status_code == 200
    assert rollout_export.status_code == 200
    assert audit_logs.status_code == 200
    export_records = [
        item
        for item in audit_logs.json()["items"]
        if item["action"] == "published_surface.evidence_bundle.export"
    ]
    records_by_bundle_id = {
        item["metadata"]["evidence_bundle"]["bundle_id"]: item for item in export_records
    }
    assert set(records_by_bundle_id) == {request_bundle_id, rollout_bundle_id}
    request_record = records_by_bundle_id[request_bundle_id]
    assert request_record["resource_type"] == "published_surface_evidence_bundle"
    assert request_record["resource_id"] == 501
    assert request_record["request_id"] == "req_export_request_bundle"
    assert request_record["metadata"]["export_format"] == "redacted_json"
    assert request_record["metadata"]["redacted_payload_summary"] == {
        "kind": "request_log",
        "request_log_id": route_test.json()["request_log"]["id"],
        "status": 200,
        "trace_id": route_test.json()["request_log"]["trace_id"],
    }
    assert "redact-me" not in str(request_record)
    rollout_record = records_by_bundle_id[rollout_bundle_id]
    assert rollout_record["request_id"] == "req_export_rollout_bundle"
    assert rollout_record["metadata"]["redacted_payload_summary"] == {
        "kind": "rollout",
        "rollout_id": rollout.json()["rollout"]["id"],
        "operation": "traffic_split",
    }


def test_evidence_bundles_are_persisted_with_export_lifecycle_state() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-918", "secret": "redact-me"},
        },
    )
    request_bundle_id = route_test.json()["request_log"]["evidence_bundle"]["bundle_id"]

    before_export = _persisted_evidence_bundle(request_bundle_id)
    export = client.get(
        f"/v1/console/published-surfaces/501/evidence-bundles/{request_bundle_id}",
        headers={**admin_headers(), "X-Request-Id": "req_persisted_export"},
    )
    after_export = _persisted_evidence_bundle(request_bundle_id)

    assert route_test.status_code == 200
    assert before_export is not None
    assert before_export.surface_id == 501
    assert before_export.bundle_id == request_bundle_id
    assert before_export.resource_type == "published_surface_request_log"
    assert before_export.status == "recorded"
    assert before_export.export_status == "not_exported"
    assert before_export.evidence_bundle_json["bundle_id"] == request_bundle_id
    assert export.status_code == 200
    assert after_export is not None
    assert after_export.export_status == "exported"
    assert after_export.last_exported_at is not None
    assert after_export.last_export_request_id == "req_persisted_export"
    assert after_export.redacted_payload_summary_json == {
        "kind": "request_log",
        "request_log_id": route_test.json()["request_log"]["id"],
        "status": 200,
        "trace_id": route_test.json()["request_log"]["trace_id"],
    }
    assert "redact-me" not in str(after_export.redacted_payload_summary_json)


def test_evidence_bundles_can_be_archived_with_retention_lifecycle_state() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-919", "secret": "redact-me"},
        },
    )
    request_bundle_id = route_test.json()["request_log"]["evidence_bundle"]["bundle_id"]

    archive = client.post(
        f"/v1/console/published-surfaces/501/evidence-bundles/{request_bundle_id}/archive",
        headers={**admin_headers(), "X-Request-Id": "req_archive_bundle"},
        json={
            "retention_policy_id": "gateway-evidence-30d",
            "retention_days": 30,
            "archive_reason": "Retain the route-test evidence for incident review.",
        },
    )
    persisted = _persisted_evidence_bundle(request_bundle_id)
    catalog = client.get(
        "/v1/console/published-surfaces/501/evidence-bundles",
        headers=admin_headers(),
    )
    audit_logs = client.get("/v1/audit-logs", headers=admin_headers())

    assert route_test.status_code == 200
    assert archive.status_code == 200
    body = archive.json()
    assert body["status"] == "archived"
    assert body["evidence_bundle"]["bundle_id"] == request_bundle_id
    assert body["retention"]["policy_id"] == "gateway-evidence-30d"
    assert body["retention"]["retention_days"] == 30
    assert body["retention"]["retain_until"] is not None
    assert body["audit"] == {
        "action": "published_surface.evidence_bundle.archive",
        "resource_type": "published_surface_evidence_bundle",
        "resource_id": request_bundle_id,
        "surface_id": 501,
        "request_id": "req_archive_bundle",
    }
    assert persisted is not None
    assert persisted.status == "archived"
    assert persisted.retention_policy_id == "gateway-evidence-30d"
    assert persisted.retain_until is not None
    assert persisted.archived_at is not None
    assert persisted.archive_reason == "Retain the route-test evidence for incident review."
    assert persisted.archive_request_id == "req_archive_bundle"
    catalog_item = {
        item["bundle_id"]: item for item in catalog.json()["items"]
    }[request_bundle_id]
    assert catalog_item["lifecycle"]["status"] == "archived"
    assert catalog_item["lifecycle"]["retention_policy_id"] == "gateway-evidence-30d"
    assert catalog_item["lifecycle"]["retain_until"] is not None
    assert catalog_item["lifecycle"]["archived_at"] is not None
    archive_records = [
        item
        for item in audit_logs.json()["items"]
        if item["action"] == "published_surface.evidence_bundle.archive"
    ]
    assert len(archive_records) == 1
    assert archive_records[0]["request_id"] == "req_archive_bundle"
    assert archive_records[0]["metadata"]["retention"]["retention_days"] == 30
    assert "redact-me" not in str(archive_records[0])


def test_console_lists_evidence_bundle_catalog_with_export_links() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-914", "secret": "redact-me"},
        },
    )
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 85, "candidate": 15},
            "audit_reason": "catalog rollout evidence bundle",
        },
    )

    catalog = client.get(
        "/v1/console/published-surfaces/501/evidence-bundles",
        headers=admin_headers(),
    )
    cross_surface = client.get(
        "/v1/console/published-surfaces/502/evidence-bundles",
        headers=admin_headers(),
    )

    assert route_test.status_code == 200
    assert rollout.status_code == 200
    request_bundle = route_test.json()["request_log"]["evidence_bundle"]
    rollout_bundle = rollout.json()["rollout"]["evidence_bundle"]
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["surface_id"] == 501
    assert body["count"] == 2
    assert body["audit"]["action"] == "published_surface.evidence_bundle.list"
    items_by_id = {item["bundle_id"]: item for item in body["items"]}
    assert set(items_by_id) == {
        request_bundle["bundle_id"],
        rollout_bundle["bundle_id"],
    }
    request_item = items_by_id[request_bundle["bundle_id"]]
    assert request_item["resource_type"] == "published_surface_request_log"
    assert request_item["request_log_id"] == request_bundle["request_log_id"]
    assert request_item["trace_id"] == request_bundle["trace_id"]
    assert request_item["export_url"] == (
        f"/v1/console/published-surfaces/501/evidence-bundles/{request_bundle['bundle_id']}"
    )
    assert request_item["audit_index"] == {
        "action": "published_surface.evidence_bundle.record",
        "resource_type": "published_surface_evidence_bundle",
        "recorded": True,
    }
    rollout_item = items_by_id[rollout_bundle["bundle_id"]]
    assert rollout_item["resource_type"] == "published_surface_rollout"
    assert rollout_item["rollout_id"] == rollout_bundle["rollout_id"]
    assert rollout_item["operation"] == "traffic_split"
    assert rollout_item["audit_index"]["recorded"] is True
    assert cross_surface.status_code == 200
    assert cross_surface.json()["items"] == []


def test_evidence_bundles_are_indexed_in_audit_log() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer sk_live"},
            "body": {"ticket_id": "INC-908", "secret": "redact-me"},
        },
    )
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 75, "candidate": 25},
            "audit_reason": "index rollout evidence bundle",
        },
    )
    audit_logs = client.get("/v1/audit-logs", headers=admin_headers())

    assert route_test.status_code == 200
    assert rollout.status_code == 200
    assert audit_logs.status_code == 200
    request_bundle = route_test.json()["request_log"]["evidence_bundle"]
    rollout_bundle = rollout.json()["rollout"]["evidence_bundle"]
    evidence_records = [
        item
        for item in audit_logs.json()["items"]
        if item["action"] == "published_surface.evidence_bundle.record"
    ]
    bundle_ids = {item["metadata"]["evidence_bundle"]["bundle_id"] for item in evidence_records}
    assert request_bundle["bundle_id"] in bundle_ids
    assert rollout_bundle["bundle_id"] in bundle_ids
    request_record = next(
        item
        for item in evidence_records
        if item["metadata"]["evidence_bundle"]["bundle_id"] == request_bundle["bundle_id"]
    )
    rollout_record = next(
        item
        for item in evidence_records
        if item["metadata"]["evidence_bundle"]["bundle_id"] == rollout_bundle["bundle_id"]
    )
    assert request_record["resource_type"] == "published_surface_evidence_bundle"
    assert request_record["resource_id"] == 501
    assert request_record["metadata"]["evidence_bundle"]["resource_type"] == (
        "published_surface_request_log"
    )
    assert request_record["metadata"]["evidence_bundle"]["redaction"] == {
        "headers": ["authorization"],
        "body": "keys_only",
    }
    assert "redact-me" not in str(request_record)
    assert rollout_record["resource_type"] == "published_surface_evidence_bundle"
    assert rollout_record["resource_id"] == 501
    assert rollout_record["metadata"]["evidence_bundle"]["resource_type"] == (
        "published_surface_rollout"
    )
    assert rollout_record["metadata"]["evidence_bundle"]["audit_scope"] == {
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }


def test_live_ingress_enforces_published_surface_rate_limit_with_429_evidence() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["rate_limit_policy"] = {"requests_per_minute": 1}

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    first = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_ingress_first"},
        json={"ticket_id": "INC-905"},
    )
    second = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_ingress_second"},
        json={"ticket_id": "INC-906"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert first.status_code == 200
    assert second.status_code == 429
    body = second.json()
    assert body["status"] == "blocked"
    assert body["blocked_reasons"] == ["rate_limited"]
    assert body["rate_limit"] == {
        "limit": 1,
        "remaining": 0,
        "retry_after_seconds": 60,
    }
    assert second.headers["X-RateLimit-Limit"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert second.headers["Retry-After"] == "60"
    assert second.headers["X-Request-Id"] == "req_ingress_second"
    assert second.headers["X-DimooRun-Trace-Id"] == body["trace_id"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rate-limit",
    }
    assert body["request_log_id"] == detail.json()["request_logs"][0]["id"]
    request_log = detail.json()["request_logs"][0]
    assert request_log["ingress_source"] == "live_http"
    assert request_log["status"] == 429
    assert request_log["policy_result"] == "deny"
    assert request_log["blocked_reasons"] == ["rate_limited"]
    assert request_log["run_id"] is None
    assert request_log["task_id"] is None
    assert request_log["rate_limit"] == body["rate_limit"]
    assert request_log["evidence_bundle"]["rate_limit"] == body["rate_limit"]
    assert request_log["evidence_bundle"]["policy_decision"] == body["policy_decision"]


def test_live_ingress_records_traffic_split_and_shadow_routing_decision() -> None:
    client = TestClient(create_app())

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    split = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 0, "candidate": 100},
            "audit_reason": "send all live ingress to candidate branch",
        },
    )
    shadow = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "shadow_mode",
            "route_id": 701,
            "shadow_mode": True,
            "audit_reason": "mirror live ingress for comparison",
        },
    )
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_live_control"},
        json={"ticket_id": "INC-907"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert split.status_code == 200
    assert shadow.status_code == 200
    assert ingress.status_code == 200
    decision = ingress.json()["traffic_control_decision"]
    assert decision == {
        "selected_branch": "candidate",
        "traffic_split": {"stable": 0, "candidate": 100},
        "shadow_mirror": True,
        "shadow_route_id": 701,
    }
    request_log = detail.json()["request_logs"][0]
    assert request_log["ingress_source"] == "live_http"
    assert request_log["traffic_control_decision"] == decision
    assert request_log["evidence_bundle"]["traffic_control"] == {
        "traffic_split": {"stable": 0, "candidate": 100},
        "shadow_mode": True,
        "shadow_route_id": 701,
    }


def test_surface_detail_reports_live_exposure_health_from_real_ingress() -> None:
    client = TestClient(create_app())

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=valid_surface_payload(),
    )
    live_ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_health_ok"},
        json={"ticket_id": "INC-920"},
    )
    healthy_detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())
    revoke = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "Stop public exposure after health probe.",
        },
    )
    blocked_ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_health_blocked"},
        json={"ticket_id": "INC-921"},
    )
    revoked_detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert live_ingress.status_code == 200
    healthy = healthy_detail.json()["exposure_health"]
    assert healthy == {
        "status": "ready",
        "route_path": "/support/triage",
        "published": True,
        "last_live_request_status": 200,
        "last_live_request_id": live_ingress.json()["request_log_id"],
        "last_live_trace_id": live_ingress.json()["trace_id"],
        "blocked_reasons": [],
    }
    assert revoke.status_code == 200
    assert blocked_ingress.status_code == 403
    revoked = revoked_detail.json()["exposure_health"]
    assert revoked["status"] == "blocked"
    assert revoked["published"] is False
    assert revoked["last_live_request_status"] == 403
    assert revoked["last_live_request_id"] == blocked_ingress.json()["request_log_id"]
    assert revoked["last_live_trace_id"] == blocked_ingress.json()["trace_id"]
    assert revoked["blocked_reasons"] == ["surface_revoked"]


def test_live_ingress_uses_active_policy_engine_decision() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "deny-published-surface-ingress",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "ingress.invoke",
                "decision": "deny",
                "priority": 1,
                "condition": {"environment": "local"},
                "reason": "Ingress is frozen during incident review.",
            },
            "audit_reason": "Freeze external ingress during incident review.",
        },
    )
    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_policy_denied"},
        json={"ticket_id": "INC-903"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert policy.status_code == 201
    policy_id = policy.json()["item"]["id"]
    assert publish.status_code == 200
    assert ingress.status_code == 403
    body = ingress.json()
    assert body["status"] == "blocked"
    assert body["blocked_reasons"] == ["Ingress is frozen during incident review."]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": str(policy_id),
        "reason": "Ingress is frozen during incident review.",
    }
    assert body["request_log_id"] == detail.json()["request_logs"][0]["id"]
    request_log = detail.json()["request_logs"][0]
    assert request_log["status"] == 403
    assert request_log["policy_result"] == "deny"
    assert request_log["blocked_reasons"] == ["Ingress is frozen during incident review."]
    assert request_log["run_id"] is None
    assert request_log["task_id"] is None
    assert request_log["evidence_bundle"]["policy_decision"] == body["policy_decision"]


def test_live_ingress_blocks_policy_approval_required_with_request_log_evidence() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "approve-published-surface-ingress",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "ingress.invoke",
                "decision": "require_approval",
                "priority": 1,
                "condition": {"environment": "local"},
                "reason": "Live ingress requires approval during incident review.",
            },
            "audit_reason": "Require approval for external ingress during review.",
        },
    )
    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_policy_approval"},
        json={"ticket_id": "INC-911"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert policy.status_code == 201
    policy_id = policy.json()["item"]["id"]
    assert publish.status_code == 200
    assert ingress.status_code == 403
    body = ingress.json()
    assert body["policy_decision"] == {
        "result": "require_approval",
        "policy_id": str(policy_id),
        "reason": "Live ingress requires approval during incident review.",
        "approval_required": True,
    }
    assert body["blocked_reasons"] == ["Live ingress requires approval during incident review."]
    request_log = detail.json()["request_logs"][0]
    assert request_log["status"] == 403
    assert request_log["run_id"] is None
    assert request_log["task_id"] is None
    assert request_log["evidence_bundle"]["policy_decision"] == body["policy_decision"]


def test_live_ingress_records_policy_redaction_and_limit_decision_evidence() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    redaction_policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "redact-published-surface-ingress",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "ingress.invoke",
                "decision": "allow_with_redaction",
                "priority": 5,
                "condition": {"environment": "local"},
                "metadata": {"redactions": ["headers.authorization", "body.secret"]},
                "reason": "Ingress may proceed with credential redaction.",
            },
            "audit_reason": "Require extra redaction for live ingress.",
        },
    )
    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    redacted_ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_policy_redact"},
        json={"ticket_id": "INC-915", "secret": "redact-me"},
    )
    redaction_detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert redaction_policy.status_code == 201
    assert publish.status_code == 200
    redaction_policy_id = redaction_policy.json()["item"]["id"]
    assert redacted_ingress.status_code == 200
    redacted_body = redacted_ingress.json()
    assert redacted_body["policy_decision"] == {
        "result": "allow_with_redaction",
        "policy_id": str(redaction_policy_id),
        "reason": "Ingress may proceed with credential redaction.",
        "redactions": ["headers.authorization", "body.secret"],
    }
    redaction_log = redaction_detail.json()["request_logs"][0]
    assert redaction_log["policy_result"] == "allow_with_redaction"
    assert redaction_log["policy_effects"] == {
        "redactions": ["headers.authorization", "body.secret"]
    }
    assert redaction_log["evidence_bundle"]["policy_decision"] == redacted_body["policy_decision"]

    limit_policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "limit-published-surface-ingress",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "ingress.invoke",
                "decision": "allow_with_limit",
                "priority": 1,
                "condition": {"environment": "local"},
                "metadata": {"limits": {"requests_per_minute": 12, "burst": 2}},
                "reason": "Ingress may proceed with stricter policy limits.",
            },
            "audit_reason": "Limit live ingress while monitoring.",
        },
    )
    limited_ingress = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_policy_limit"},
        json={"ticket_id": "INC-916"},
    )
    limit_detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert limit_policy.status_code == 201
    limit_policy_id = limit_policy.json()["item"]["id"]
    assert limited_ingress.status_code == 200
    limited_body = limited_ingress.json()
    assert limited_body["policy_decision"] == {
        "result": "allow_with_limit",
        "policy_id": str(limit_policy_id),
        "policy_ids": [str(limit_policy_id), str(redaction_policy_id)],
        "reason": "Ingress may proceed with stricter policy limits.",
        "limits": {"requests_per_minute": 12, "burst": 2},
        "redactions": ["headers.authorization", "body.secret"],
    }
    limit_log = limit_detail.json()["request_logs"][0]
    assert limit_log["policy_result"] == "allow_with_limit"
    assert limit_log["policy_effects"] == {
        "limits": {"requests_per_minute": 12, "burst": 2},
        "redactions": ["headers.authorization", "body.secret"],
    }
    assert limit_log["evidence_bundle"]["policy_decision"] == limited_body["policy_decision"]


def test_publish_uses_active_policy_engine_decision_without_creating_surface() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "deny-published-surface-publish",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "publish",
                "decision": "deny",
                "priority": 1,
                "condition": {"environment": "local"},
                "reason": "External publishing is frozen for this environment.",
            },
            "audit_reason": "Freeze external publishing during incident review.",
        },
    )
    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert policy.status_code == 201
    policy_id = policy.json()["item"]["id"]
    assert publish.status_code == 200
    body = publish.json()
    assert body["status"] == "blocked"
    assert body["can_publish"] is False
    assert body["surface"] is None
    assert body["rollout"] is None
    assert body["blocked_reasons"] == ["External publishing is frozen for this environment."]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": str(policy_id),
        "reason": "External publishing is frozen for this environment.",
    }
    assert body["audit_preview"]["action"] == "published_surface.publish.blocked"
    assert body["impact_preview"]["expected_runtime_effect"] == "external_traffic_not_exposed"
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_publish_blocks_policy_approval_required_without_creating_surface() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()

    policy = client.post(
        "/v1/policies/activate",
        headers=admin_headers(),
        json={
            "draft_policy": {
                "name": "approve-published-surface-publish",
                "type": "gateway",
                "resource_type": "published_surface",
                "action": "publish",
                "decision": "require_approval",
                "priority": 1,
                "condition": {"environment": "local"},
                "reason": "External publishing requires gateway approval.",
            },
            "audit_reason": "Require approval for external publishing.",
        },
    )
    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert policy.status_code == 201
    policy_id = policy.json()["item"]["id"]
    assert publish.status_code == 200
    body = publish.json()
    assert body["status"] == "blocked"
    assert body["can_publish"] is False
    assert body["surface"] is None
    assert body["rollout"] is None
    assert body["policy_decision"] == {
        "result": "require_approval",
        "policy_id": str(policy_id),
        "reason": "External publishing requires gateway approval.",
        "approval_required": True,
    }
    assert body["blocked_reasons"] == ["External publishing requires gateway approval."]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_route_test_blocks_rate_limited_requests_with_request_log_evidence() -> None:
    client = TestClient(create_app())
    payload = valid_surface_payload()
    surface = payload["surface"]
    assert isinstance(surface, dict)
    surface["rate_limit_policy"] = {"requests_per_minute": 1}

    publish = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=payload,
    )
    first = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    second = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert publish.status_code == 200
    assert first.status_code == 200
    assert first.json()["status"] == "matched"
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["status"] == "blocked"
    assert "rate_limited" in second_body["blocked_reasons"]
    assert second_body["expected_runtime_task"] is None
    assert second_body["request_log"]["status"] == 429
    assert second_body["request_log"]["policy_result"] == "deny"
    assert second_body["request_log"]["run_id"] is None
    assert detail.status_code == 200
    assert detail.json()["request_logs"][0]["status"] == 429
    assert detail.json()["request_logs"][0]["blocked_reasons"] == ["rate_limited"]


def test_route_test_blocks_inactive_surfaces_with_request_log_evidence() -> None:
    client = TestClient(create_app())

    disabled = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={"operation": "disable", "audit_reason": "maintenance window"},
    )
    disabled_route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    publish_second = valid_surface_payload()
    second_surface = publish_second["surface"]
    assert isinstance(second_surface, dict)
    second_surface["surface_id"] = 502
    second_surface["route_path"] = "/support/escalate"
    published_second = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=publish_second,
    )
    revoked = client.post(
        "/v1/published-surfaces/502/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 502",
            "audit_reason": "public key compromise",
        },
    )
    revoked_route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 502,
            "route_id": 701,
            "path": "/support/escalate",
            "method": "POST",
        },
    )
    disabled_detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())
    revoked_detail = client.get("/v1/console/published-surfaces/502", headers=admin_headers())

    assert disabled.status_code == 200
    assert published_second.status_code == 200
    assert revoked.status_code == 200
    for route_test, reason in [
        (disabled_route_test, "surface_disabled"),
        (revoked_route_test, "surface_revoked"),
    ]:
        assert route_test.status_code == 200
        body = route_test.json()
        assert body["status"] == "blocked"
        assert body["expected_runtime_task"] is None
        assert reason in body["blocked_reasons"]
        assert body["request_log"]["status"] == 403
        assert body["request_log"]["policy_result"] == "deny"
        assert body["request_log"]["run_id"] is None
        assert body["request_log"]["task_id"] is None
    assert disabled_detail.status_code == 200
    assert revoked_detail.status_code == 200
    assert disabled_detail.json()["request_logs"][0]["blocked_reasons"] == ["surface_disabled"]
    assert revoked_detail.json()["request_logs"][0]["blocked_reasons"] == ["surface_revoked"]


def test_route_test_blocks_malformed_route_identifiers_without_server_error() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": "surface",
            "route_id": True,
            "path": "/support/triage",
            "method": "POST",
        },
    )

    assert route_test.status_code == 200
    body = route_test.json()
    assert body["status"] == "blocked"
    assert body["matched_deployment"] is None
    assert body["auth_decision"]["result"] == "not_evaluated"
    assert body["policy_decision"]["result"] == "not_evaluated"
    assert body["expected_runtime_task"] is None
    assert body["request_log"] is None
    assert "surface_id_invalid" in body["blocked_reasons"]
    assert "route_id_invalid" in body["blocked_reasons"]
    assert body["audit"]["resource_id"] is None


def test_route_test_blocks_unmatched_path_and_method_without_request_log() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/admin/delete-all",
            "method": "TRACE",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert route_test.status_code == 200
    body = route_test.json()
    assert body["status"] == "blocked"
    assert body["matched_deployment"] is None
    assert body["auth_decision"]["result"] == "not_evaluated"
    assert body["policy_decision"]["result"] == "not_evaluated"
    assert body["expected_runtime_task"] is None
    assert body["request_log"] is None
    assert "route_not_found" in body["blocked_reasons"]
    assert "method_not_allowed" in body["blocked_reasons"]
    assert body["audit"]["resource_id"] is None
    assert detail.status_code == 200
    assert detail.json()["request_logs"] == []


def test_console_published_surface_detail_returns_logs_and_rollout_history() -> None:
    client = TestClient(create_app())
    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    assert route_test.status_code == 200
    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80, "candidate": 20},
            "audit_reason": "canary support ingress",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert rollout.status_code == 200
    assert detail.status_code == 200
    body = detail.json()
    assert body["surface"]["id"] == 501
    assert body["deployment_binding_health"]["status"] == "ready"
    assert body["request_logs"][0]["status"] == 200
    assert body["request_logs"][0]["run_id"] == 9001
    assert body["request_logs"][0]["task_id"] == 8001
    assert body["request_logs"][0]["trace_id"].startswith("trace_")
    assert body["rollout_history"][-1]["operation"] == "traffic_split"
    assert body["rollout_history"][-1]["traffic_split"]["candidate"] == 20
    assert body["actions"]["revoke"]["requires_confirmation"] is True


def test_rollout_history_records_action_decision_snapshot() -> None:
    client = TestClient(create_app())

    rollout = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80, "candidate": 20},
            "audit_reason": "canary support ingress",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert rollout.status_code == 200
    rollout_entry = rollout.json()["rollout"]
    assert rollout_entry["permission_summary"] == {
        "required_permission": "published_surface.traffic_split",
        "actor_permission": "allowed",
    }
    assert rollout_entry["policy_decision"] == {
        "result": "allow",
        "policy_id": "published-surface-rollout-controls",
    }
    assert rollout_entry["audit_preview"]["action"] == "published_surface.traffic_split"
    assert rollout_entry["impact_preview"]["affected_resources"] == [
        "published_surface:501",
        "deployment:10",
        "ingress_route:701",
    ]
    assert rollout_entry["impact_preview"]["expected_runtime_effect"] == (
        "traffic_distribution_changes"
    )
    assert rollout_entry["audit_scope"] == {
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert rollout.json()["audit"] == {
        "action": "published_surface.traffic_split",
        "resource_type": "published_surface",
        "resource_id": 501,
        "request_id": "req_published",
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert detail.status_code == 200
    assert detail.json()["rollout_history"][-1] == rollout_entry


def test_console_published_surface_actions_include_policy_and_audit_metadata() -> None:
    client = TestClient(create_app())

    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert detail.status_code == 200
    actions = detail.json()["actions"]
    for action_name in ("revoke", "traffic_split", "rollback"):
        action = actions[action_name]
        assert action["audit_required"] is True
        assert action["policy_decision"] == {
            "result": "allow",
            "policy_id": "published-surface-rollout-controls",
        }
        assert action["audit_preview"] == {
            "action": f"published_surface.{action_name}",
            "resource_type": "published_surface",
            "resource_id": 501,
        }
    assert actions["rollback"]["recovery_path"] == "restore_previous_surface_snapshot"


def test_console_published_surface_actions_include_impact_and_permission_summary() -> None:
    client = TestClient(create_app())

    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert detail.status_code == 200
    actions = detail.json()["actions"]
    for action_name in ("revoke", "traffic_split", "rollback"):
        action = actions[action_name]
        assert action["permission_summary"] == {
            "required_permission": f"published_surface.{action_name}",
            "actor_permission": "allowed",
        }
        assert action["impact_preview"]["surface_id"] == 501
        assert action["impact_preview"]["affected_resources"] == [
            "published_surface:501",
            "deployment:10",
            "ingress_route:701",
        ]
        assert action["impact_preview"]["last_known_health"] == "ready"
        assert action["impact_preview"]["requires_audit_reason"] is True
    assert (
        actions["revoke"]["impact_preview"]["expected_runtime_effect"]
        == "external_traffic_denied"
    )
    assert (
        actions["traffic_split"]["impact_preview"]["expected_runtime_effect"]
        == "traffic_distribution_changes"
    )
    assert (
        actions["rollback"]["impact_preview"]["expected_runtime_effect"]
        == "surface_snapshot_restored"
    )


def test_console_request_log_drilldown_returns_scoped_log_evidence() -> None:
    client = TestClient(create_app())

    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={
            "surface_id": 501,
            "route_id": 701,
            "path": "/support/triage",
            "method": "POST",
            "headers": {"authorization": "Bearer secret"},
        },
    )
    log_id = route_test.json()["request_log"]["id"]
    drilldown = client.get(
        f"/v1/console/published-surfaces/501/request-logs/{log_id}",
        headers=admin_headers(),
    )
    cross_surface = client.get(
        f"/v1/console/published-surfaces/502/request-logs/{log_id}",
        headers=admin_headers(),
    )
    unknown = client.get(
        "/v1/console/published-surfaces/501/request-logs/999999",
        headers=admin_headers(),
    )

    assert route_test.status_code == 200
    assert drilldown.status_code == 200
    body = drilldown.json()
    assert body["request_log"]["id"] == log_id
    assert body["request_log"]["surface_id"] == 501
    assert body["request_log"]["redacted_request_metadata"]["headers"]["authorization"] == (
        "[REDACTED]"
    )
    assert body["audit"]["action"] == "published_surface.request_log.view"
    assert body["audit"]["resource_id"] == log_id
    assert cross_surface.status_code == 404
    assert cross_surface.json()["error_code"] == "request_log_not_found"
    assert unknown.status_code == 404
    assert unknown.json()["error_code"] == "request_log_not_found"


def test_rollout_controls_revoke_and_block_missing_confirmation() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={"operation": "revoke", "confirmation": "revoke"},
    )
    revoked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "compromised public credential",
        },
    )
    rollback = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "rollback",
            "rollback_to_version": 1,
            "audit_reason": "restore previous ingress route",
        },
    )

    assert blocked.status_code == 409
    blocked_body = blocked.json()
    assert blocked_body["error_code"] == "dangerous_surface_action_confirmation_required"
    assert blocked_body["required_confirmation"] == "REVOKE SURFACE 501"
    assert blocked_body["blocked_reasons"] == ["confirmation_required"]
    assert blocked_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert blocked_body["permission_summary"] == {
        "required_permission": "published_surface.revoke",
        "actor_permission": "allowed",
    }
    assert blocked_body["audit_preview"]["action"] == "published_surface.revoke.blocked"
    assert blocked_body["impact_preview"]["blocked_reasons"] == ["confirmation_required"]
    assert revoked.status_code == 200
    assert revoked.json()["surface"]["status"] == "revoked"
    assert revoked.json()["audit"]["action"] == "published_surface.revoke"
    assert rollback.status_code == 200
    assert rollback.json()["rollout"]["operation"] == "rollback"
    assert rollback.json()["rollout"]["rollback_to_version"] == 1


def test_rollout_blocks_revoke_without_audit_reason_before_state_change() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={"operation": "revoke", "confirmation": "REVOKE SURFACE 501"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "rollout_audit_reason_required"
    assert body["blocked_reasons"] == ["audit_reason_required"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.revoke",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.revoke.blocked"
    assert body["impact_preview"]["blocked_reasons"] == ["audit_reason_required"]
    assert detail.status_code == 200
    assert detail.json()["surface"]["status"] == "active"
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_repeated_revoke_with_disabled_action_reason() -> None:
    client = TestClient(create_app())

    revoked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "compromised public credential",
        },
    )
    repeated = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "duplicate revoke attempt",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert revoked.status_code == 200
    assert repeated.status_code == 409
    repeated_body = repeated.json()
    assert repeated_body["error_code"] == "surface_already_revoked"
    assert repeated_body["blocked_reasons"] == ["already_revoked"]
    assert repeated_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert repeated_body["permission_summary"] == {
        "required_permission": "published_surface.revoke",
        "actor_permission": "allowed",
    }
    assert repeated_body["audit_preview"]["action"] == "published_surface.revoke.blocked"
    assert repeated_body["impact_preview"]["blocked_reasons"] == ["already_revoked"]
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["actions"]["revoke"]["disabled_reason"] == "already_revoked"
    assert [item["operation"] for item in detail_body["rollout_history"]] == ["revoke"]


def test_console_action_model_explains_controls_disabled_after_revoke() -> None:
    client = TestClient(create_app())

    revoke = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "public endpoint compromised",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert revoke.status_code == 200
    assert detail.status_code == 200
    actions = detail.json()["actions"]
    assert actions["disable"]["disabled_reason"] == "surface_revoked"
    assert actions["traffic_split"]["disabled_reason"] == "surface_revoked"
    assert actions["shadow_mode"]["disabled_reason"] == "surface_revoked"
    assert actions["rollback"]["disabled_reason"] is None


def test_console_action_model_explains_controls_disabled_after_disable() -> None:
    client = TestClient(create_app())

    disable = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "disable",
            "audit_reason": "pause public ingress during maintenance",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert disable.status_code == 200
    assert detail.status_code == 200
    actions = detail.json()["actions"]
    assert actions["enable"]["disabled_reason"] is None
    assert actions["disable"]["disabled_reason"] == "already_disabled"
    assert actions["traffic_split"]["disabled_reason"] == "surface_disabled"
    assert actions["shadow_mode"]["disabled_reason"] == "surface_disabled"
    assert actions["rollback"]["disabled_reason"] is None


def test_rollout_blocks_traffic_controls_on_disabled_surface_without_history() -> None:
    client = TestClient(create_app())

    disabled = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "disable",
            "audit_reason": "pause public ingress during maintenance",
        },
    )
    split = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80, "candidate": 20},
            "audit_reason": "attempt canary while inactive",
        },
    )
    shadow = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "shadow_mode",
            "route_id": 701,
            "shadow_mode": True,
            "audit_reason": "attempt shadow while inactive",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert disabled.status_code == 200
    assert split.status_code == 409
    assert split.json()["error_code"] == "surface_inactive"
    assert split.json()["blocked_reasons"] == ["surface_disabled"]
    split_body = split.json()
    assert split_body["permission_summary"] == {
        "required_permission": "published_surface.traffic_split",
        "actor_permission": "allowed",
    }
    assert split_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert split_body["audit_preview"]["action"] == "published_surface.traffic_split.blocked"
    assert split_body["impact_preview"]["surface_id"] == 501
    assert split_body["impact_preview"]["blocked_reasons"] == ["surface_disabled"]
    assert shadow.status_code == 409
    assert shadow.json()["error_code"] == "surface_inactive"
    assert shadow.json()["blocked_reasons"] == ["surface_disabled"]
    assert detail.status_code == 200
    assert [item["operation"] for item in detail.json()["rollout_history"]] == ["disable"]


def test_rollout_blocks_repeated_disable_without_history() -> None:
    client = TestClient(create_app())

    disabled = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "disable",
            "audit_reason": "pause public ingress during maintenance",
        },
    )
    repeated = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "disable",
            "audit_reason": "duplicate maintenance pause",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert disabled.status_code == 200
    assert repeated.status_code == 409
    repeated_body = repeated.json()
    assert repeated_body["error_code"] == "surface_already_disabled"
    assert repeated_body["blocked_reasons"] == ["already_disabled"]
    assert repeated_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert repeated_body["permission_summary"] == {
        "required_permission": "published_surface.disable",
        "actor_permission": "allowed",
    }
    assert repeated_body["audit_preview"]["action"] == "published_surface.disable.blocked"
    assert repeated_body["impact_preview"]["blocked_reasons"] == ["already_disabled"]
    assert detail.status_code == 200
    assert [item["operation"] for item in detail.json()["rollout_history"]] == ["disable"]


def test_rollout_blocks_repeated_enable_without_history() -> None:
    client = TestClient(create_app())

    repeated = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "enable",
            "audit_reason": "duplicate public ingress resume",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert repeated.status_code == 409
    repeated_body = repeated.json()
    assert repeated_body["error_code"] == "surface_already_active"
    assert repeated_body["blocked_reasons"] == ["already_active"]
    assert repeated_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert repeated_body["permission_summary"] == {
        "required_permission": "published_surface.enable",
        "actor_permission": "allowed",
    }
    assert repeated_body["audit_preview"]["action"] == "published_surface.enable.blocked"
    assert repeated_body["impact_preview"]["blocked_reasons"] == ["already_active"]
    assert detail.status_code == 200
    assert detail.json()["surface"]["status"] == "active"
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_enable_after_revoke_without_history() -> None:
    client = TestClient(create_app())

    revoked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "revoke",
            "confirmation": "REVOKE SURFACE 501",
            "audit_reason": "credential leak",
        },
    )
    enabled = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "enable",
            "audit_reason": "unsafe re-enable after revoke",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert revoked.status_code == 200
    assert enabled.status_code == 409
    enabled_body = enabled.json()
    assert enabled_body["error_code"] == "surface_revoked"
    assert enabled_body["blocked_reasons"] == ["surface_revoked"]
    assert enabled_body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert enabled_body["permission_summary"] == {
        "required_permission": "published_surface.enable",
        "actor_permission": "allowed",
    }
    assert enabled_body["audit_preview"]["action"] == "published_surface.enable.blocked"
    assert enabled_body["impact_preview"]["blocked_reasons"] == ["surface_revoked"]
    assert detail.status_code == 200
    assert detail.json()["surface"]["status"] == "revoked"
    assert detail.json()["actions"]["enable"]["disabled_reason"] == "surface_revoked"
    assert [item["operation"] for item in detail.json()["rollout_history"]] == ["revoke"]


def test_rollout_rollback_restores_previous_published_surface_version() -> None:
    client = TestClient(create_app())
    v1 = valid_surface_payload()
    v1_surface = v1["surface"]
    assert isinstance(v1_surface, dict)
    v1_surface["deployment_id"] = 41
    v1_surface["environment"] = "staging"
    v1_surface["auth_mode"] = "jwt"
    v1_surface["route_path"] = "/support/v1"
    v2 = valid_surface_payload()
    v2_surface = v2["surface"]
    assert isinstance(v2_surface, dict)
    v2_surface["deployment_id"] = 42
    v2_surface["environment"] = "production"
    v2_surface["auth_mode"] = "oauth"
    v2_surface["route_path"] = "/support/v2"

    published_v1 = client.post("/v1/published-surfaces/publish", headers=admin_headers(), json=v1)
    published_v2 = client.post("/v1/published-surfaces/publish", headers=admin_headers(), json=v2)
    rollback = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "rollback",
            "rollback_to_version": 1,
            "audit_reason": "restore previous ingress contract",
        },
    )
    restored_route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/v1", "method": "POST"},
    )
    stale_route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/v2", "method": "POST"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert published_v1.status_code == 200
    assert published_v2.status_code == 200
    assert rollback.status_code == 200
    rollback_body = rollback.json()
    assert rollback_body["surface"]["deployment_id"] == 41
    assert rollback_body["surface"]["environment"] == "staging"
    assert rollback_body["surface"]["auth_mode"] == "jwt"
    assert rollback_body["surface"]["route_path"] == "/support/v1"
    assert rollback_body["rollout"]["operation"] == "rollback"
    assert rollback_body["rollout"]["rollback_to_version"] == 1
    assert rollback_body["rollout"]["restored_version"] == 1
    assert rollback_body["audit"]["action"] == "published_surface.rollback"
    assert restored_route_test.status_code == 200
    restored_body = restored_route_test.json()
    assert restored_body["status"] == "matched"
    assert restored_body["matched_deployment"]["deployment_id"] == 41
    assert restored_body["matched_deployment"]["environment"] == "staging"
    assert restored_body["auth_decision"]["mode"] == "jwt"
    assert stale_route_test.status_code == 200
    assert stale_route_test.json()["status"] == "blocked"
    assert "route_not_found" in stale_route_test.json()["blocked_reasons"]
    assert detail.status_code == 200
    assert detail.json()["surface"]["route_path"] == "/support/v1"


def test_rollback_records_live_ingress_compatibility_evidence() -> None:
    client = TestClient(create_app())
    v1 = valid_surface_payload()
    v2 = valid_surface_payload()
    v2_surface = v2["surface"]
    assert isinstance(v2_surface, dict)
    v2_surface["deployment_id"] = 44
    v2_surface["route_path"] = "/support/escalate"
    v2_surface["auth_mode"] = "jwt"

    publish_v1 = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=v1,
    )
    publish_v2 = client.post(
        "/v1/published-surfaces/publish",
        headers=admin_headers(),
        json=v2,
    )
    rollback = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "rollback",
            "rollback_to_version": 1,
            "audit_reason": "Restore the original public route after candidate failure.",
        },
    )
    old_route = client.post(
        "/v1/ingress/support/triage",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_old_route"},
        json={"ticket_id": "INC-909"},
    )
    new_route = client.post(
        "/v1/ingress/support/escalate",
        headers={"Authorization": "Bearer runtime-token", "X-Request-Id": "req_new_route"},
        json={"ticket_id": "INC-910"},
    )

    assert publish_v1.status_code == 200
    assert publish_v2.status_code == 200
    assert rollback.status_code == 200
    rollout = rollback.json()["rollout"]
    assert rollout["operation"] == "rollback"
    assert rollout["restored_version"] == 1
    assert rollout["live_gateway_verification"] == {
        "status": "ready_for_live_ingress",
        "verification_mode": "in_process_route_binding",
        "restored_route_path": "/support/triage",
        "restored_deployment_id": 10,
        "restored_environment": "local",
        "restored_auth_mode": "api_key",
    }
    assert rollout["evidence_bundle"]["live_gateway_verification"] == (
        rollout["live_gateway_verification"]
    )
    assert old_route.status_code == 200
    assert old_route.json()["matched_deployment"]["deployment_id"] == 10
    assert old_route.json()["runtime_task"]["path"] == "/support/triage"
    assert new_route.status_code == 404
    assert new_route.json()["blocked_reasons"] == ["route_not_found"]


def test_rollout_controls_route_shadow_mode_with_audit_evidence() -> None:
    client = TestClient(create_app())

    shadow = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "shadow_mode",
            "route_id": 701,
            "shadow_mode": True,
            "audit_reason": "mirror traffic before public rollout",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert shadow.status_code == 200
    body = shadow.json()
    assert body["rollout"]["operation"] == "shadow_mode"
    assert body["rollout"]["route_id"] == 701
    assert body["rollout"]["shadow_mode"] is True
    assert body["audit"]["action"] == "published_surface.shadow_mode"
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["rollout_history"][-1]["operation"] == "shadow_mode"
    assert detail_body["rollout_history"][-1]["route_id"] == 701
    assert detail_body["actions"]["shadow_mode"]["disabled_reason"] is None


def test_route_test_records_traffic_split_and_shadow_mode_decision_evidence() -> None:
    client = TestClient(create_app())

    split = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 75, "candidate": 25},
            "audit_reason": "canary public ingress",
        },
    )
    shadow = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "shadow_mode",
            "route_id": 701,
            "shadow_mode": True,
            "audit_reason": "mirror route before rollout",
        },
    )
    route_test = client.post(
        "/v1/ingress-routes/test",
        headers=admin_headers(),
        json={"surface_id": 501, "route_id": 701, "path": "/support/triage", "method": "POST"},
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert split.status_code == 200
    assert shadow.status_code == 200
    assert route_test.status_code == 200
    body = route_test.json()
    assert body["traffic_control"] == {
        "traffic_split": {"stable": 75, "candidate": 25},
        "shadow_mode": True,
        "shadow_route_id": 701,
    }
    assert body["request_log"]["traffic_control"] == body["traffic_control"]
    assert detail.status_code == 200
    assert detail.json()["request_logs"][0]["traffic_control"] == body["traffic_control"]


def test_rollout_blocks_invalid_route_shadow_mode_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "shadow_mode",
            "route_id": "071",
            "shadow_mode": "true",
            "audit_reason": "invalid shadow mode controls",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "invalid_shadow_mode"
    assert "route_id_invalid" in body["blocked_reasons"]
    assert "shadow_mode_invalid" in body["blocked_reasons"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.shadow_mode",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.shadow_mode.blocked"
    assert body["impact_preview"]["blocked_reasons"] == body["blocked_reasons"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_invalid_traffic_split_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 120, "candidate": -20},
            "audit_reason": "invalid canary split",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "invalid_traffic_split"
    assert "traffic_split_negative" in body["blocked_reasons"]
    assert "traffic_split_total_invalid" in body["blocked_reasons"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.traffic_split",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.traffic_split.blocked"
    assert body["impact_preview"]["blocked_reasons"] == body["blocked_reasons"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_non_integral_traffic_split_without_history_entry() -> None:
    client = TestClient(create_app())

    fractional = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80.5, "candidate": 19.5},
            "audit_reason": "invalid fractional canary split",
        },
    )
    leading_zero = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": "080", "candidate": "020"},
            "audit_reason": "invalid leading zero canary split",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert fractional.status_code == 409
    assert fractional.json()["error_code"] == "invalid_traffic_split"
    assert "traffic_split_total_invalid" in fractional.json()["blocked_reasons"]
    assert leading_zero.status_code == 409
    assert leading_zero.json()["error_code"] == "invalid_traffic_split"
    assert "traffic_split_total_invalid" in leading_zero.json()["blocked_reasons"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_missing_audit_reason_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "traffic_split",
            "traffic_split": {"stable": 80, "candidate": 20},
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "rollout_audit_reason_required"
    assert body["blocked_reasons"] == ["audit_reason_required"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.traffic_split",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.traffic_split.blocked"
    assert body["audit"] == {
        "action": "published_surface.traffic_split.blocked",
        "resource_type": "published_surface",
        "resource_id": 501,
        "request_id": "req_published",
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert body["impact_preview"]["blocked_reasons"] == ["audit_reason_required"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_unsupported_operation_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "promote",
            "audit_reason": "unsupported surface operation",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "unsupported_rollout_operation"
    assert body["blocked_reasons"] == ["rollout_operation_unsupported"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.promote",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.promote.blocked"
    assert body["audit"] == {
        "action": "published_surface.promote.blocked",
        "resource_type": "published_surface",
        "resource_id": 501,
        "request_id": "req_published",
        "tenant_id": 1,
        "project_id": 1,
        "environment": "local",
    }
    assert body["impact_preview"]["blocked_reasons"] == [
        "rollout_operation_unsupported"
    ]
    assert body["impact_preview"]["expected_runtime_effect"] == (
        "unsupported_operation_blocked"
    )
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_invalid_rollback_target_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "rollback",
            "rollback_to_version": "previous",
            "audit_reason": "invalid rollback target",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "invalid_rollback_target"
    assert body["blocked_reasons"] == ["rollback_target_invalid"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.rollback",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.rollback.blocked"
    assert body["impact_preview"]["blocked_reasons"] == ["rollback_target_invalid"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []


def test_rollout_blocks_unknown_rollback_target_without_history_entry() -> None:
    client = TestClient(create_app())

    blocked = client.post(
        "/v1/published-surfaces/501/rollout",
        headers=admin_headers(),
        json={
            "operation": "rollback",
            "rollback_to_version": 99,
            "audit_reason": "unknown rollback target",
        },
    )
    detail = client.get("/v1/console/published-surfaces/501", headers=admin_headers())

    assert blocked.status_code == 409
    body = blocked.json()
    assert body["error_code"] == "rollback_target_not_found"
    assert body["blocked_reasons"] == ["rollback_target_not_found"]
    assert body["policy_decision"] == {
        "result": "deny",
        "policy_id": "published-surface-rollout-controls",
    }
    assert body["permission_summary"] == {
        "required_permission": "published_surface.rollback",
        "actor_permission": "allowed",
    }
    assert body["audit_preview"]["action"] == "published_surface.rollback.blocked"
    assert body["impact_preview"]["blocked_reasons"] == ["rollback_target_not_found"]
    assert detail.status_code == 200
    assert detail.json()["rollout_history"] == []
