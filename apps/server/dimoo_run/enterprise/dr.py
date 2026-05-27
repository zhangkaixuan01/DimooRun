from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.artifacts.store import ArtifactChecksumMismatchError, ArtifactRecord
from dimoo_run.observability.audit import InMemoryComplianceAuditLog


class RestoreValidationError(RuntimeError):
    error_code = "restore_validation_failed"


@dataclass(frozen=True)
class BackupPlan:
    id: str
    tenant_id: str
    project_id: str | None
    name: str
    scope: str
    targets: list[str]
    schedule: str
    retention_days: int
    storage_ref: str
    status: str = "active"
    created_by: str | None = None
    rpo_seconds: int | None = None
    rto_seconds: int | None = None


@dataclass(frozen=True)
class RestoreValidationReport:
    id: str
    backup_ref: str
    restore_scope: str
    passed: bool
    checks: list[dict[str, Any]]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class RestoreJob:
    id: str
    tenant_id: str
    project_id: str | None
    backup_ref: str
    restore_scope: str
    status: str
    backup_plan_id: str | None = None
    validation_report: RestoreValidationReport | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BackupRestoreService:
    def __init__(self, *, audit_log: InMemoryComplianceAuditLog) -> None:
        self.audit_log = audit_log
        self.plans: dict[str, BackupPlan] = {}
        self.restore_jobs: dict[str, RestoreJob] = {}

    def create_plan(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        scope: str,
        targets: list[str],
        schedule: str,
        retention_days: int,
        storage_ref: str,
        created_by: str | None,
        rpo_seconds: int | None = None,
        rto_seconds: int | None = None,
    ) -> BackupPlan:
        if scope not in {"tenant", "project", "platform"}:
            raise ValueError("backup_scope_invalid")
        if scope == "project" and project_id is None:
            raise ValueError("project_backup_requires_project_id")
        plan = BackupPlan(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            scope=scope,
            targets=targets,
            schedule=schedule,
            retention_days=retention_days,
            storage_ref=storage_ref,
            created_by=created_by,
            rpo_seconds=rpo_seconds,
            rto_seconds=rto_seconds,
        )
        self.plans[plan.id] = plan
        return plan

    def dry_run_restore(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        backup_ref: str,
        restore_scope: str,
        artifacts: list[tuple[ArtifactRecord, bytes]],
        actor_id: str | None,
        backup_plan_id: str | None = None,
    ) -> RestoreJob:
        if backup_plan_id is not None:
            plan = self.plans.get(backup_plan_id)
            if plan is None:
                raise RestoreValidationError("backup_plan_not_found")
            if plan.tenant_id != tenant_id or plan.project_id != project_id:
                raise RestoreValidationError("backup_plan_scope_mismatch")
            if plan.scope != restore_scope:
                raise RestoreValidationError("backup_plan_restore_scope_mismatch")
        for record, _data in artifacts:
            if record.tenant_id != tenant_id or record.project_id != project_id:
                raise RestoreValidationError("artifact_scope_mismatch")
        started_at = datetime.now(UTC)
        checks = [_validate_artifact(record, data) for record, data in artifacts]
        passed = all(check["passed"] for check in checks)
        report = RestoreValidationReport(
            id=str(uuid4()),
            backup_ref=backup_ref,
            restore_scope=restore_scope,
            passed=passed,
            checks=checks,
        )
        status = "dry_run_passed" if passed else "dry_run_failed"
        job = RestoreJob(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            backup_ref=backup_ref,
            restore_scope=restore_scope,
            status=status,
            backup_plan_id=backup_plan_id,
            validation_report=report,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        self.restore_jobs[job.id] = job
        self.audit_log.record(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            actor_type="user" if actor_id else "system",
            action="restore.dry_run",
            resource_type="restore_job",
            resource_id=job.id,
            result="allow" if passed else "deny",
            metadata={"backup_ref": backup_ref, "restore_scope": restore_scope, "passed": passed},
        )
        return job


def _validate_artifact(record: ArtifactRecord, data: bytes) -> dict[str, Any]:
    import hashlib

    checksum = f"sha256:{hashlib.sha256(data).hexdigest()}"
    passed = checksum == record.checksum and record.size_bytes == len(data)
    if not passed:
        return {
            "target": "artifact",
            "artifact_id": record.id,
            "passed": False,
            "reason": ArtifactChecksumMismatchError.error_code,
        }
    return {"target": "artifact", "artifact_id": record.id, "passed": True}
