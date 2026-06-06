import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


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
