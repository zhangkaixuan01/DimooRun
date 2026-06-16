import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.api.native.runtime import reset_native_runtime
from dimoo_run.server import create_app
from fastapi.testclient import TestClient


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-ops-{uuid4().hex}.db"
    reset_api_key_authenticator()
    reset_native_runtime()


def admin_headers(request_id: str = "req_ops") -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": request_id,
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "local",
    }


def admin_headers_without_project_scope() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": "req_ops_unscoped",
        "X-Tenant-Id": "1",
        "X-Environment": "local",
    }


def admin_headers_without_environment_scope() -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Request-Id": "req_ops_no_environment",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }


def test_incident_acknowledge_and_resolve_return_timeline_evidence_and_delivery_attempts() -> None:
    client = TestClient(create_app())

    acknowledged = client.post(
        "/v1/incidents/201/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalated provider outage.",
            "linked_runs": [1001],
            "linked_tasks": [8001],
            "linked_events": ["evt-1001-attempt"],
            "notify_channels": ["pagerduty-primary"],
        },
    )
    resolved = client.post(
        "/v1/incidents/201/resolve",
        headers=admin_headers(),
        json={
            "audit_note": "Provider recovered and replay succeeded.",
            "resolution_summary": "Rerouted traffic to healthy gateway.",
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert acknowledged.status_code == 200
    assert resolved.status_code == 200
    ack_body = acknowledged.json()
    resolve_body = resolved.json()
    assert ack_body["incident"]["id"] == 201
    assert ack_body["incident"]["status"] == "acknowledged"
    assert ack_body["timeline"][-1]["action"] == "incident.acknowledge"
    assert ack_body["timeline"][-1]["audit_note"] == "Escalated provider outage."
    assert ack_body["linked_evidence"]["runs"] == [1001]
    assert ack_body["linked_evidence"]["tasks"] == [8001]
    assert ack_body["linked_evidence"]["events"] == ["evt-1001-attempt"]
    assert ack_body["delivery_attempts"][0]["status"] == "sent"
    assert ack_body["audit"]["action"] == "incident.acknowledge"
    assert resolve_body["incident"]["status"] == "resolved"
    assert resolve_body["timeline"][-1]["action"] == "incident.resolve"
    assert resolve_body["resolution"]["summary"] == "Rerouted traffic to healthy gateway."
    assert resolve_body["audit"]["action"] == "incident.resolve"


def test_incident_acknowledge_blocks_missing_audit_note() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/202/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": " ",
            "linked_runs": [1001],
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_audit_note_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == ["audit_note_present"]
    assert body["disabled_action_reason"] == "audit_note_required"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_resolve_blocks_missing_resolution_summary() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/203/resolve",
        headers=admin_headers(),
        json={
            "audit_note": "Provider recovery verified.",
            "resolution_summary": " ",
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_resolution_summary_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == ["audit_note_present", "resolution_summary_present"]
    assert body["disabled_action_reason"] == "resolution_summary_required"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []
    assert body["resolution"] is None


def test_incident_acknowledge_blocks_invalid_notify_channels() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/204/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted without a valid notification channel.",
            "linked_runs": [1001],
            "notify_channels": ["  "],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_notify_channels_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == ["audit_note_present", "notify_channels_valid"]
    assert body["validation"]["notify_channels_valid"] is False
    assert body["disabled_action_reason"] == "notify_channels_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_acknowledge_blocks_partially_blank_notify_channels() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/204/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted with a partially blank notification channel.",
            "linked_runs": [1001],
            "notify_channels": ["pagerduty-primary", "  "],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_notify_channels_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["notify_channels_valid"] is False
    assert body["validation"]["invalid_notify_channels"] == ["  "]
    assert body["disabled_action_reason"] == "notify_channels_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_acknowledge_blocks_invalid_linked_evidence_ids() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/205/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted with malformed linked evidence.",
            "linked_runs": ["not-a-run-id"],
            "linked_tasks": [8001],
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_linked_evidence_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "audit_note_present",
        "linked_evidence_valid",
    ]
    assert body["validation"]["linked_evidence_valid"] is False
    assert body["validation"]["invalid_linked_evidence_fields"] == ["linked_runs"]
    assert body["disabled_action_reason"] == "linked_evidence_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_acknowledge_blocks_partially_blank_linked_run_ids() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/205/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted with partially blank linked run evidence.",
            "linked_runs": [1001, "  "],
            "linked_tasks": [8001],
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_linked_evidence_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["linked_evidence_valid"] is False
    assert body["validation"]["invalid_linked_evidence_fields"] == ["linked_runs"]
    assert body["validation"]["invalid_linked_evidence_values"] == {
        "linked_runs": ["  "]
    }
    assert body["disabled_action_reason"] == "linked_evidence_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_acknowledge_blocks_blank_linked_events() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/206/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted with blank linked event evidence.",
            "linked_runs": [1001],
            "linked_events": ["  "],
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_linked_evidence_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "audit_note_present",
        "linked_evidence_valid",
    ]
    assert body["validation"]["linked_evidence_valid"] is False
    assert body["validation"]["invalid_linked_evidence_fields"] == ["linked_events"]
    assert body["disabled_action_reason"] == "linked_evidence_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_incident_acknowledge_blocks_partially_blank_linked_events() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/incidents/206/acknowledge",
        headers=admin_headers(),
        json={
            "audit_note": "Escalation attempted with partially blank linked event evidence.",
            "linked_runs": [1001],
            "linked_events": ["evt-1001-attempt", "  "],
            "notify_channels": ["pagerduty-primary"],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "incident_linked_evidence_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["linked_evidence_valid"] is False
    assert body["validation"]["invalid_linked_evidence_fields"] == ["linked_events"]
    assert body["validation"]["invalid_linked_evidence_values"] == {
        "linked_events": ["  "]
    }
    assert body["disabled_action_reason"] == "linked_evidence_invalid"
    assert body["timeline"] == []
    assert body["delivery_attempts"] == []


def test_notification_test_send_records_delivery_attempt_visibility() -> None:
    client = TestClient(create_app())

    sent = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "pagerduty-primary",
            "target_ref": "pd://service/runtime",
            "message": "Synthetic notification probe",
        },
    )

    assert sent.status_code == 200
    body = sent.json()
    assert body["status"] == "sent"
    assert body["delivery_attempt"]["channel_id"] == 55
    assert body["delivery_attempt"]["target_ref"] == "pd://service/runtime"
    assert body["delivery_attempt"]["visible_to_operator"] is True
    assert body["delivery_attempt"]["redacted_payload"]["message"] == "Synthetic notification probe"
    assert body["audit"]["action"] == "notification.test_send"


def test_alert_rule_test_records_delivery_attempt() -> None:
    client = TestClient(create_app())
    channel = client.post(
        "/v1/notifications/channels",
        headers=admin_headers("req_alert_channel"),
        json={"name": "ops-alerts", "target_ref": "slack://ops-alerts", "type": "webhook"},
    )
    assert channel.status_code == 201
    rule = client.post(
        "/v1/alerts/rules",
        headers=admin_headers("req_alert_rule"),
        json={
            "name": "runtime error burst",
            "signal": "runtime.error_rate",
            "threshold": 2,
            "channel_id": channel.json()["item"]["id"],
        },
    )
    assert rule.status_code == 201

    response = client.post(
        f"/v1/alerts/rules/{rule.json()['item']['id']}/test",
        headers=admin_headers("req_alert_test"),
        json={"audit_reason": "verify alert route"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_attempt"]["visible_to_operator"] is True
    assert body["request_id"] == "req_alert_test"


def test_webhook_validate_redacts_secret_reference() -> None:
    client = TestClient(create_app())
    subscription = client.post(
        "/v1/webhooks/subscriptions",
        headers=admin_headers("req_webhook_create"),
        json={
            "name": "runtime events",
            "target_url": "https://hooks.example.test/runtime",
            "secret_ref": "secret:prod/webhooks/runtime",
            "event_types": ["run.failed"],
        },
    )
    assert subscription.status_code == 201

    response = client.post(
        f"/v1/webhooks/subscriptions/{subscription.json()['item']['id']}/validate",
        headers=admin_headers("req_webhook_validate"),
        json={"audit_reason": "verify webhook target"},
    )

    assert response.status_code == 200
    body = response.json()
    body_text = str(body).lower()
    assert "secret:prod/webhooks/runtime" not in body_text
    assert "[redacted]" in body_text
    assert body["audit"]["action"] == "webhook_subscription.validate"


def test_notification_test_send_blocks_missing_target_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "pagerduty-primary",
            "target_ref": "",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_target_ref_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "target_ref_present",
        "target_ref_valid",
        "message_present",
        "channel_id_valid",
        "channel_name_valid",
    ]
    assert body["validation"]["target_ref_valid"] is True
    assert body["validation"]["channel_id_valid"] is True
    assert body["validation"]["channel_name_valid"] is True
    assert body["disabled_action_reason"] == "target_ref_required"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_invalid_target_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "pagerduty-primary",
            "target_ref": "runtime-service",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_target_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "target_ref_present",
        "target_ref_valid",
        "message_present",
        "channel_id_valid",
        "channel_name_valid",
    ]
    assert body["validation"]["target_ref_valid"] is False
    assert body["disabled_action_reason"] == "target_ref_invalid"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_padded_target_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "pagerduty-primary",
            "target_ref": " pd://service/runtime ",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_target_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["target_ref_present"] is True
    assert body["validation"]["target_ref_valid"] is False
    assert body["validation"]["target_ref_normalized"] == "pd://service/runtime"
    assert body["disabled_action_reason"] == "target_ref_invalid"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_missing_message() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "pagerduty-primary",
            "target_ref": "pd://service/runtime",
            "message": "  ",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_message_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "target_ref_present",
        "target_ref_valid",
        "message_present",
        "channel_id_valid",
        "channel_name_valid",
    ]
    assert body["validation"]["target_ref_valid"] is True
    assert body["validation"]["channel_id_valid"] is True
    assert body["validation"]["channel_name_valid"] is True
    assert body["disabled_action_reason"] == "message_required"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_invalid_channel_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": "pagerduty-primary",
            "channel_name": "pagerduty-primary",
            "target_ref": "pd://service/runtime",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_channel_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "target_ref_present",
        "target_ref_valid",
        "message_present",
        "channel_id_valid",
        "channel_name_valid",
    ]
    assert body["validation"]["target_ref_valid"] is True
    assert body["validation"]["channel_id_valid"] is False
    assert body["validation"]["channel_name_valid"] is True
    assert body["disabled_action_reason"] == "channel_id_invalid"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_padded_channel_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": " 55 ",
            "channel_name": "pagerduty-primary",
            "target_ref": "pd://service/runtime",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_channel_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["channel_id_valid"] is False
    assert body["validation"]["channel_id_normalized"] == 55
    assert body["disabled_action_reason"] == "channel_id_invalid"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_blank_channel_name() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": "  ",
            "target_ref": "pd://service/runtime",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_channel_name_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "target_ref_present",
        "target_ref_valid",
        "message_present",
        "channel_id_valid",
        "channel_name_valid",
    ]
    assert body["validation"]["target_ref_valid"] is True
    assert body["validation"]["channel_name_valid"] is False
    assert body["disabled_action_reason"] == "channel_name_invalid"
    assert body["delivery_attempt"] is None


def test_notification_test_send_blocks_padded_channel_name() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/notifications/test-send",
        headers=admin_headers(),
        json={
            "channel_id": 55,
            "channel_name": " pagerduty-primary ",
            "target_ref": "pd://service/runtime",
            "message": "Synthetic notification probe",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "notification_channel_name_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["channel_name_valid"] is False
    assert body["validation"]["channel_name_normalized"] == "pagerduty-primary"
    assert body["disabled_action_reason"] == "channel_name_invalid"
    assert body["delivery_attempt"] is None


def test_backup_and_restore_dry_runs_prove_scope_and_block_destructive_restore() -> None:
    client = TestClient(create_app())

    backup = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 9,
            "scope": "project",
            "targets": ["runs", "datasets", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )
    blocked_restore = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": True,
            "confirmation": "restore",
        },
    )
    allowed_restore = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": True,
            "confirmation": "RESTORE PROJECT 1",
        },
    )

    assert backup.status_code == 200
    backup_body = backup.json()
    assert backup_body["status"] == "ready"
    assert backup_body["scope_proof"]["tenant_id"] == 1
    assert backup_body["scope_proof"]["project_id"] == 1
    assert backup_body["scope_proof"]["backup_scope"] == "project"
    assert backup_body["validation"]["valid"] is True
    assert backup_body["audit"]["action"] == "backup.dry_run"
    assert blocked_restore.status_code == 409
    blocked_body = blocked_restore.json()
    assert blocked_body["error_code"] == "destructive_restore_confirmation_required"
    assert blocked_body["validation"]["valid"] is False
    assert blocked_body["validation"]["destructive_confirmation_required"] == "RESTORE PROJECT 1"
    assert blocked_body["disabled_action_reason"] == "destructive_restore_confirmation_required"
    assert allowed_restore.status_code == 200
    restore_body = allowed_restore.json()
    assert restore_body["status"] == "ready"
    assert restore_body["validation"]["valid"] is True
    assert restore_body["scope_proof"]["restore_scope"] == "project"
    assert restore_body["audit"]["action"] == "restore.dry_run"


def test_backup_dry_run_blocks_missing_scope_headers() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers_without_project_scope(),
        json={
            "plan_id": 10,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_scope_headers_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "scope_headers_present",
        "plan_id_valid",
        "storage_ref_present",
        "targets_selected",
    ]
    assert body["validation"]["missing_scope_headers"] == ["X-Project-Id"]
    assert body["validation"]["plan_id_valid"] is True
    assert body["disabled_action_reason"] == "scope_headers_required"
    assert body["scope_proof"]["tenant_id"] == 1
    assert body["scope_proof"]["project_id"] is None


def test_backup_and_restore_dry_runs_block_missing_environment_scope_header() -> None:
    client = TestClient(create_app())

    backup = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers_without_environment_scope(),
        json={
            "plan_id": 16,
            "scope": "environment",
            "targets": ["runs", "events"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )
    restore = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers_without_environment_scope(),
        json={
            "backup_ref": "backup://2026-06-05/environment",
            "restore_scope": "environment",
            "targets": ["runs"],
            "destructive": True,
            "confirmation": "RESTORE ENVIRONMENT local",
        },
    )

    assert backup.status_code == 400
    backup_body = backup.json()
    assert backup_body["error_code"] == "backup_scope_headers_required"
    assert backup_body["validation"]["valid"] is False
    assert backup_body["validation"]["missing_scope_headers"] == ["X-Environment"]
    assert backup_body["disabled_action_reason"] == "scope_headers_required"
    assert backup_body["scope_proof"]["environment"] is None
    assert restore.status_code == 400
    restore_body = restore.json()
    assert restore_body["error_code"] == "restore_scope_headers_required"
    assert restore_body["validation"]["valid"] is False
    assert restore_body["validation"]["missing_scope_headers"] == ["X-Environment"]
    assert restore_body["validation"]["destructive_confirmation_required"] == (
        "RESTORE ENVIRONMENT unknown"
    )
    assert restore_body["disabled_action_reason"] == "scope_headers_required"
    assert restore_body["scope_proof"]["environment"] is None


def test_backup_dry_run_blocks_missing_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 13,
            "scope": "project",
            "targets": [],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is False
    assert body["disabled_action_reason"] == "backup_targets_required"


def test_backup_dry_run_blocks_blank_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 13,
            "scope": "project",
            "targets": ["runs", " "],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == [" "]
    assert body["disabled_action_reason"] == "backup_targets_invalid"


def test_backup_dry_run_blocks_padded_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 13,
            "scope": "project",
            "targets": ["runs", " audit_logs "],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == [" audit_logs "]
    assert body["validation"]["unsupported_targets"] == []
    assert body["disabled_action_reason"] == "backup_targets_invalid"


def test_backup_dry_run_blocks_non_string_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 13,
            "scope": "project",
            "targets": ["runs", None],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == ["None"]
    assert body["validation"]["unsupported_targets"] == []
    assert body["disabled_action_reason"] == "backup_targets_invalid"


def test_backup_dry_run_blocks_non_list_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 13,
            "scope": "project",
            "targets": "runs",
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is False
    assert body["validation"]["invalid_targets"] == ["runs"]
    assert body["disabled_action_reason"] == "backup_targets_invalid"


def test_backup_dry_run_blocks_invalid_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 11,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "local-backups/project",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["allowed_storage_ref_schemes"] == ["s3://", "minio://"]
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_shallow_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 19,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3:///",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_identity_present"] is False
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_bucket_only_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 20,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_identity_present"] is False
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_empty_segment_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 21,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups//local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_identity_present"] is False
    assert body["validation"]["storage_ref_normalized"] == "s3://dimoorun-backups//local"
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_traversal_segment_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 22,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/../local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_identity_present"] is False
    assert body["validation"]["storage_ref_normalized"] == "s3://dimoorun-backups/../local"
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_query_segment_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 23,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local?temporary=true",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_identity_present"] is False
    assert (
        body["validation"]["storage_ref_normalized"]
        == "s3://dimoorun-backups/local?temporary=true"
    )
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_padded_storage_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 18,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": " s3://dimoorun-backups/local ",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_storage_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["storage_ref_valid"] is False
    assert body["validation"]["storage_ref_normalized"] == "s3://dimoorun-backups/local"
    assert body["disabled_action_reason"] == "storage_ref_invalid"


def test_backup_dry_run_blocks_invalid_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": "nightly",
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_boolean_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": True,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] is None
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_fractional_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 9.5,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] is None
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_non_positive_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 0,
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] is None
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_signed_string_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": "+9",
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] is None
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_leading_zero_string_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": "09",
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] is None
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_padded_plan_id() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": " 9 ",
            "scope": "project",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_plan_id_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["plan_id_valid"] is False
    assert body["validation"]["plan_id_normalized"] == 9
    assert body["disabled_action_reason"] == "backup_plan_id_invalid"


def test_backup_dry_run_blocks_unsupported_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 14,
            "scope": "database",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_scope_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["scope_valid"] is False
    assert body["validation"]["allowed_scopes"] == [
        "organization",
        "tenant",
        "project",
        "environment",
    ]
    assert body["disabled_action_reason"] == "backup_scope_invalid"


def test_backup_dry_run_blocks_blank_explicit_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 14,
            "scope": "",
            "targets": ["runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_scope_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["scope_valid"] is False
    assert body["validation"]["scope_normalized"] is None
    assert body["disabled_action_reason"] == "backup_scope_invalid"


def test_backup_dry_run_blocks_unknown_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 12,
            "scope": "project",
            "targets": ["runs", "secrets"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["unsupported_targets"] == ["secrets"]
    assert body["validation"]["allowed_targets"] == [
        "audit_logs",
        "datasets",
        "events",
        "runs",
        "tasks",
    ]
    assert body["disabled_action_reason"] == "backup_targets_invalid"


def test_backup_dry_run_blocks_duplicate_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/dry-run",
        headers=admin_headers(),
        json={
            "plan_id": 15,
            "scope": "project",
            "targets": ["runs", "runs", "audit_logs"],
            "storage_ref": "s3://dimoorun-backups/local",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "backup_targets_duplicate"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["duplicate_targets"] == ["runs"]
    assert body["disabled_action_reason"] == "backup_targets_duplicate"


def test_restore_dry_run_blocks_missing_scope_headers() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers_without_project_scope(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_scope_headers_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["checks"] == [
        "backup_ref_present",
        "scope_headers_present",
        "backup_ref_scope_present",
        "scope_matches_backup",
        "targets_selected",
        "confirmation",
    ]
    assert body["validation"]["missing_scope_headers"] == ["X-Project-Id"]
    assert body["disabled_action_reason"] == "scope_headers_required"
    assert body["scope_proof"]["tenant_id"] == 1
    assert body["scope_proof"]["project_id"] is None


def test_restore_dry_run_blocks_invalid_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "local/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["allowed_backup_ref_prefix"] == "backup://"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_shallow_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["allowed_backup_ref_prefix"] == "backup://"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_backup_ref_without_identity_before_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup:///project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_identity_present"] is False
    assert body["validation"]["backup_scope"] == "project"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_empty_segment_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05//project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_identity_present"] is False
    assert body["validation"]["backup_ref_normalized"] == "backup://2026-06-05//project"
    assert body["validation"]["backup_scope"] == "project"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_trailing_slash_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project/",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_identity_present"] is False
    assert body["validation"]["backup_ref_normalized"] == "backup://2026-06-05/project/"
    assert body["validation"]["backup_scope"] == "project"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_traversal_segment_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/../project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_identity_present"] is False
    assert body["validation"]["backup_ref_normalized"] == "backup://2026-06-05/../project"
    assert body["validation"]["backup_scope"] == "project"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_query_segment_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project?temporary=true",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_identity_present"] is False
    assert (
        body["validation"]["backup_ref_normalized"]
        == "backup://2026-06-05/project?temporary=true"
    )
    assert body["validation"]["backup_scope"] is None
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_padded_backup_ref() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": " backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_ref_valid"] is False
    assert body["validation"]["backup_ref_normalized"] == "backup://2026-06-05/project"
    assert body["disabled_action_reason"] == "backup_ref_invalid"


def test_restore_dry_run_blocks_backup_ref_without_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_backup_ref_scope_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_scope"] is None
    assert body["validation"]["backup_ref_scope_present"] is False
    assert body["validation"]["allowed_restore_scopes"] == [
        "organization",
        "tenant",
        "project",
        "environment",
    ]
    assert body["disabled_action_reason"] == "backup_ref_scope_required"


def test_restore_dry_run_blocks_missing_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": [],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_required"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is False
    assert body["disabled_action_reason"] == "restore_targets_required"


def test_restore_dry_run_blocks_blank_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs", " "],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == [" "]
    assert body["disabled_action_reason"] == "restore_targets_invalid"


def test_restore_dry_run_blocks_padded_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs", " tasks "],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == [" tasks "]
    assert body["validation"]["unsupported_targets"] == []
    assert body["disabled_action_reason"] == "restore_targets_invalid"


def test_restore_dry_run_blocks_non_string_target_items() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs", None],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is True
    assert body["validation"]["invalid_targets"] == ["None"]
    assert body["validation"]["unsupported_targets"] == []
    assert body["disabled_action_reason"] == "restore_targets_invalid"


def test_restore_dry_run_blocks_non_list_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": "runs",
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["targets_selected"] is False
    assert body["validation"]["invalid_targets"] == ["runs"]
    assert body["disabled_action_reason"] == "restore_targets_invalid"


def test_restore_dry_run_blocks_unknown_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs", "secrets"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["unsupported_targets"] == ["secrets"]
    assert body["validation"]["allowed_targets"] == [
        "audit_logs",
        "datasets",
        "events",
        "runs",
        "tasks",
    ]
    assert body["disabled_action_reason"] == "restore_targets_invalid"


def test_restore_dry_run_blocks_duplicate_targets() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs", "runs", "events"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_targets_duplicate"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["duplicate_targets"] == ["runs"]
    assert body["disabled_action_reason"] == "restore_targets_duplicate"


def test_restore_dry_run_blocks_backup_scope_mismatch() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/organization",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "restore_scope_mismatch"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["backup_scope"] == "organization"
    assert body["validation"]["restore_scope"] == "project"
    assert body["validation"]["checks"] == [
        "backup_ref_present",
        "scope_headers_present",
        "backup_ref_scope_present",
        "scope_matches_backup",
        "targets_selected",
        "confirmation",
    ]
    assert body["disabled_action_reason"] == "restore_scope_mismatch"


def test_restore_dry_run_blocks_unsupported_restore_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/database",
            "restore_scope": "database",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_scope_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["restore_scope_valid"] is False
    assert body["validation"]["allowed_restore_scopes"] == [
        "organization",
        "tenant",
        "project",
        "environment",
    ]
    assert body["disabled_action_reason"] == "restore_scope_invalid"


def test_restore_dry_run_blocks_blank_explicit_scope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "",
            "targets": ["runs"],
            "destructive": False,
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_scope_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["restore_scope_valid"] is False
    assert body["validation"]["restore_scope_normalized"] is None
    assert body["disabled_action_reason"] == "restore_scope_invalid"


def test_restore_dry_run_uses_scope_specific_destructive_confirmation() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/tenant",
            "restore_scope": "tenant",
            "targets": ["runs"],
            "destructive": True,
            "confirmation": "RESTORE TENANT 1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["validation"]["valid"] is True
    assert body["validation"]["destructive_confirmation_required"] == "RESTORE TENANT 1"
    assert body["scope_proof"]["restore_scope"] == "tenant"
    assert body["scope_proof"]["tenant_id"] == 1


def test_restore_dry_run_blocks_malformed_destructive_flag() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/v1/backups/restore-dry-run",
        headers=admin_headers(),
        json={
            "backup_ref": "backup://2026-06-05/project",
            "restore_scope": "project",
            "targets": ["runs"],
            "destructive": "true",
            "confirmation": "RESTORE PROJECT 1",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "restore_destructive_flag_invalid"
    assert body["status"] == "blocked"
    assert body["validation"]["valid"] is False
    assert body["validation"]["destructive_valid"] is False
    assert body["validation"]["destructive"] is False
    assert body["disabled_action_reason"] == "destructive_flag_invalid"
