import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from dimoo_run.artifacts.store import (
    ArtifactChecksumMismatchError,
    LocalArtifactStore,
    S3CompatibleArtifactStore,
)
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.enums import DeploymentDesiredStatus
from dimoo_run.enterprise.dr import BackupRestoreService, RestoreValidationError
from dimoo_run.extensions.webhooks import (
    InMemoryWebhookTransport,
    WebhookSubscription,
    WebhookSubscriptionService,
)
from dimoo_run.notifications.alerts import AlertRule, NotificationChannel, NotificationService
from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.observability.exporters import (
    ExporterConfig,
    InMemoryExportSink,
    ObservabilityExporter,
)
from dimoo_run.sandbox.container_pool import (
    ContainerPool,
    ContainerPoolBoundaryError,
    ContainerPoolRequest,
)
from dimoo_run.sandbox.policy import SandboxPolicy, SandboxPolicyViolation


@dataclass
class FakeObjectStoreClient:
    objects: dict[tuple[str, str], bytes] = field(default_factory=dict)
    metadata: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    presign_calls: list[dict[str, Any]] = field(default_factory=list)

    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        _ = content_type
        self.objects[(bucket, key)] = body
        self.metadata[(bucket, key)] = metadata

    def get_object(self, *, bucket: str, key: str) -> bytes:
        return self.objects[(bucket, key)]

    def presigned_get_url(self, *, bucket: str, key: str, expires_seconds: int) -> str:
        self.presign_calls.append(
            {"bucket": bucket, "key": key, "expires_seconds": expires_seconds}
        )
        return f"https://signed.example/{bucket}/{key}?expires={expires_seconds}"


def context(project_id: str | None = "project_1") -> RuntimeContext:
    return RuntimeContext(
        tenant_id="tenant_1",
        project_id=project_id,
        run_id="run_1",
        task_id="task_1",
        agent_id="agent_1",
        agent_version_id="agent_version_1",
        deployment_id="deployment_1",
        attempt_id="attempt_1",
        framework="langgraph",
    )


def test_local_artifact_store_separates_metadata_object_and_signed_download(tmp_path: Path) -> None:
    audit = InMemoryComplianceAuditLog()
    store = LocalArtifactStore(audit_log=audit, root=tmp_path, public_base_url="https://artifacts")

    record = store.write_json(
        context=context(),
        artifact_type="output_payload",
        payload={"answer": 42},
        visibility_level="restricted",
        created_by="user_1",
    )

    assert record.storage_uri.startswith("local://artifact/")
    assert (tmp_path / "objects" / f"{record.id}.json").exists()
    assert (tmp_path / "metadata" / f"{record.id}.json").exists()
    assert store.read_json(
        record.storage_uri,
        context=context(),
        permissions={"artifact:read:restricted"},
    ) == {"answer": 42}
    assert store.signed_download_url(record.storage_uri).startswith("https://artifacts/")


def test_s3_compatible_artifact_store_uses_bucket_uri_and_verifies_checksum(
    tmp_path: Path,
) -> None:
    audit = InMemoryComplianceAuditLog()
    store = S3CompatibleArtifactStore(
        audit_log=audit,
        bucket="dimoorun-artifacts",
        endpoint_url="http://minio:9000",
        root=tmp_path,
        scheme="minio",
    )

    record = store.write_json(
        context=context(),
        artifact_type="input_payload",
        payload={"question": "ok"},
        visibility_level="internal",
        created_by="user_1",
    )

    assert record.storage_uri.startswith("minio://dimoorun-artifacts/artifacts/")
    object_path = tmp_path / "objects" / f"{record.id}.json"
    object_path.write_text('{"question":"tampered"}', encoding="utf-8")
    with pytest.raises(ArtifactChecksumMismatchError):
        store.read_json(
            record.storage_uri,
            context=context(),
            permissions={"artifact:read:internal"},
        )


def test_s3_compatible_artifact_store_can_use_real_object_client_boundary(tmp_path: Path) -> None:
    audit = InMemoryComplianceAuditLog()
    object_client = FakeObjectStoreClient()
    store = S3CompatibleArtifactStore(
        audit_log=audit,
        bucket="dimoorun-artifacts",
        endpoint_url="http://minio:9000",
        root=tmp_path,
        scheme="s3",
        object_client=object_client,
    )

    record = store.write_json(
        context=context(),
        artifact_type="input_payload",
        payload={"question": "ok"},
        visibility_level="internal",
        created_by="user_1",
    )

    object_key = f"artifacts/{record.id}.json"
    assert object_client.objects[("dimoorun-artifacts", object_key)] == b'{"question":"ok"}'
    assert object_client.metadata[("dimoorun-artifacts", object_key)]["checksum"] == record.checksum
    assert store.read_json(
        record.storage_uri,
        context=context(),
        permissions={"artifact:read:internal"},
    ) == {"question": "ok"}
    assert store.signed_download_url(record.storage_uri).startswith("https://signed.example/")


def test_observability_exporter_redacts_samples_and_dead_letters_failures() -> None:
    sink = InMemoryExportSink(fail_next=True)
    exporter = ObservabilityExporter(
        config=ExporterConfig(name="otel", kind="opentelemetry"),
        sink=sink,
    )
    event = AgentEvent(
        type="tool.completed",
        run_id="run_1",
        sequence=1,
        payload={"secret": "leak", "value": 1},
    )

    assert exporter.export_event(event) is False
    assert exporter.failures[0].payload["payload"]["secret"] == "[REDACTED]"

    assert exporter.export_event(event) is True
    assert sink.payloads[0]["ledger"] == "event"


def test_backup_plan_and_restore_dry_run_validate_artifact_checksum(tmp_path: Path) -> None:
    audit = InMemoryComplianceAuditLog()
    store = LocalArtifactStore(audit_log=audit, root=tmp_path)
    record = store.write_json(
        context=context(),
        artifact_type="output_payload",
        payload={"answer": 42},
        visibility_level="internal",
        created_by="user_1",
    )
    data = json.dumps({"answer": 42}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    service = BackupRestoreService(audit_log=audit)
    plan = service.create_plan(
        tenant_id="tenant_1",
        project_id="project_1",
        name="daily",
        scope="project",
        targets=["Artifact metadata", "Artifact object data"],
        schedule="0 1 * * *",
        retention_days=7,
        storage_ref="minio://backups/project_1",
        created_by="user_1",
        rpo_seconds=300,
        rto_seconds=900,
    )

    job = service.dry_run_restore(
        tenant_id="tenant_1",
        project_id="project_1",
        backup_plan_id=plan.id,
        backup_ref="backup://daily/1",
        restore_scope="project",
        artifacts=[(record, data)],
        actor_id="user_1",
    )

    assert job.status == "dry_run_passed"
    assert job.validation_report is not None
    assert job.validation_report.passed is True
    assert audit.records[-1].action == "restore.dry_run"


def test_restore_dry_run_rejects_cross_scope_plan_and_artifacts(tmp_path: Path) -> None:
    audit = InMemoryComplianceAuditLog()
    store = LocalArtifactStore(audit_log=audit, root=tmp_path)
    record = store.write_json(
        context=context(project_id="project_2"),
        artifact_type="output_payload",
        payload={"answer": 42},
        visibility_level="internal",
        created_by="user_1",
    )
    service = BackupRestoreService(audit_log=audit)
    plan = service.create_plan(
        tenant_id="tenant_1",
        project_id="project_1",
        name="daily",
        scope="project",
        targets=["Artifact object data"],
        schedule="0 1 * * *",
        retention_days=7,
        storage_ref="minio://backups/project_1",
        created_by="user_1",
    )

    with pytest.raises(RestoreValidationError, match="artifact_scope_mismatch"):
        service.dry_run_restore(
            tenant_id="tenant_1",
            project_id="project_1",
            backup_plan_id=plan.id,
            backup_ref="backup://daily/1",
            restore_scope="project",
            artifacts=[(record, b'{"answer":42}')],
            actor_id="user_1",
        )

    with pytest.raises(RestoreValidationError, match="backup_plan_scope_mismatch"):
        service.dry_run_restore(
            tenant_id="tenant_1",
            project_id="project_2",
            backup_plan_id=plan.id,
            backup_ref="backup://daily/1",
            restore_scope="project",
            artifacts=[],
            actor_id="user_1",
        )


def test_notification_incident_ack_resolve_dedupe_and_failed_delivery() -> None:
    audit = InMemoryComplianceAuditLog()
    service = NotificationService(audit_log=audit)
    channel = service.register_channel(
        NotificationChannel(
            id="channel_1",
            tenant_id="tenant_1",
            project_id="project_1",
            type="webhook",
            target_ref="secret:webhook",
            metadata={"fail_delivery": True},
        )
    )
    service.register_rule(
        AlertRule(
            id="rule_1",
            tenant_id="tenant_1",
            project_id="project_1",
            name="failure-rate",
            signal="run_failed_rate_high",
            threshold=0.2,
            channel_id=channel.id,
            dedupe_window_seconds=300,
            cooldown_seconds=0,
        )
    )

    incident = service.evaluate_signal(
        tenant_id="tenant_1",
        project_id="project_1",
        signal="run_failed_rate_high",
        value=0.5,
        source_ref="metric://run_failed_rate",
        payload={"secret": "leak"},
    )
    duplicate = service.evaluate_signal(
        tenant_id="tenant_1",
        project_id="project_1",
        signal="run_failed_rate_high",
        value=0.7,
        source_ref="metric://run_failed_rate",
    )

    assert incident is not None
    assert duplicate is incident
    assert service.failed_deliveries[0]["reason"] == "notification_delivery_failed"
    assert incident.metadata["payload"]["secret"] == "[REDACTED]"
    acknowledged = service.acknowledge_incident(incident.id, actor_id="user_1")
    resolved = service.resolve_incident(incident.id, actor_id="user_1")
    assert acknowledged.status == "acknowledged"
    assert resolved.status == "resolved"
    assert audit.records[-1].action == "incident.resolve"


def test_webhook_subscription_dispatch_redacts_audits_and_isolates_failure() -> None:
    audit = InMemoryComplianceAuditLog()
    transport = InMemoryWebhookTransport(fail_next=True)
    service = WebhookSubscriptionService(transport=transport, audit_log=audit)
    subscription = service.subscribe(
        tenant_id="tenant_1",
        project_id="project_1",
        name="events",
        event_types={"run.completed"},
        target_url="https://example.com/webhook",
        secret_ref="secret:webhook",
        permissions={"event:receive"},
    )

    event = AgentEvent(
        type="run.completed",
        run_id="run_1",
        sequence=1,
        payload={"api_key": "leak", "ok": True},
    )

    assert subscription.public_dict()["secret_ref"] == "[REDACTED]"
    assert service.dispatch(event, tenant_id="tenant_1", project_id="project_1") == 0
    assert service.deliveries[0].status == "failed"
    assert service.dispatch(event, tenant_id="tenant_1", project_id="project_1") == 1
    assert transport.requests[0]["payload"]["payload"]["api_key"] == "[REDACTED]"
    assert audit.records[-1].action == "webhook.dispatch"


def test_webhook_rate_limit_resets_after_one_minute() -> None:
    audit = InMemoryComplianceAuditLog()
    transport = InMemoryWebhookTransport()
    service = WebhookSubscriptionService(transport=transport, audit_log=audit)
    subscription = service.subscribe(
        tenant_id="tenant_1",
        project_id="project_1",
        name="events",
        event_types={"run.completed"},
        target_url="https://example.com/webhook",
        secret_ref="secret:webhook",
        permissions={"event:receive"},
    )
    limited = WebhookSubscription(
        **{**subscription.__dict__, "rate_limit_per_minute": 1}
    )
    service.subscriptions[subscription.id] = limited
    event = AgentEvent(type="run.completed", run_id="run_1", sequence=1, payload={})

    assert service.dispatch(event, tenant_id="tenant_1", project_id="project_1") == 1
    assert service.dispatch(event, tenant_id="tenant_1", project_id="project_1") == 0
    service._delivery_windows[subscription.id] = (  # noqa: SLF001
        datetime.now(UTC) - timedelta(minutes=1, seconds=1),
        1,
    )

    assert service.dispatch(event, tenant_id="tenant_1", project_id="project_1") == 1


def test_container_pool_enforces_deployment_status_policy_and_audits() -> None:
    audit = InMemoryComplianceAuditLog()
    pool = ContainerPool(
        policy=SandboxPolicy(
            isolation_level="L3",
            network_policy="deny",
            filesystem_policy="readonly",
            allowed_env={"SAFE"},
            allowed_secret_refs={"secret:model"},
        ),
        audit_log=audit,
    )

    result = pool.run(
        ContainerPoolRequest(
            tenant_id="tenant_1",
            project_id="project_1",
            deployment_id="deployment_1",
            desired_status=DeploymentDesiredStatus.active.value,
            env={"SAFE": "1"},
            secret_refs={"secret:model"},
            resources={"cpu": "500m", "memory": "512Mi"},
        ),
        actor_id="worker_1",
        operation=lambda: {"ok": True},
    )

    assert result == {"ok": True}
    with pytest.raises(ContainerPoolBoundaryError):
        pool.run(
            ContainerPoolRequest(
                tenant_id="tenant_1",
                project_id="project_1",
                deployment_id="deployment_2",
                desired_status=DeploymentDesiredStatus.paused.value,
            ),
            actor_id="worker_1",
            operation=lambda: {"should_not_run": True},
        )
    with pytest.raises(SandboxPolicyViolation):
        pool.run(
            ContainerPoolRequest(
                tenant_id="tenant_1",
                project_id="project_1",
                deployment_id="deployment_3",
                desired_status=DeploymentDesiredStatus.active.value,
                env={"OPENAI_API_KEY": "leak"},
            ),
            actor_id="worker_1",
            operation=lambda: {"should_not_run": True},
        )
    assert [record.result for record in audit.records] == ["allow", "deny", "deny"]
