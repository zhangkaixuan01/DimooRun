import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.core.context import RuntimeContext
from dimoo_run.observability.audit import InMemoryComplianceAuditLog


class ArtifactAccessDeniedError(PermissionError):
    error_code = "artifact_access_denied"


class ArtifactChecksumMismatchError(RuntimeError):
    error_code = "artifact_checksum_mismatch"


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    tenant_id: str
    project_id: str | None
    run_id: str | None
    attempt_id: str | None
    event_id: str | None
    artifact_type: str
    mime_type: str
    size_bytes: int
    storage_uri: str
    checksum: str
    visibility_level: str
    created_by: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryArtifactStore:
    def __init__(self, *, audit_log: InMemoryComplianceAuditLog) -> None:
        self.audit_log = audit_log
        self.records: dict[str, ArtifactRecord] = {}
        self._objects: dict[str, bytes] = {}

    def write_json(
        self,
        *,
        context: RuntimeContext,
        artifact_type: str,
        payload: dict[str, Any],
        visibility_level: str,
        created_by: str | None,
        event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        artifact_id = str(uuid4())
        storage_uri = f"memory://artifact/{artifact_id}"
        record = ArtifactRecord(
            id=artifact_id,
            tenant_id=context.tenant_id,
            project_id=context.project_id,
            run_id=context.run_id,
            attempt_id=context.attempt_id,
            event_id=event_id,
            artifact_type=artifact_type,
            mime_type="application/json",
            size_bytes=len(encoded),
            storage_uri=storage_uri,
            checksum=f"sha256:{hashlib.sha256(encoded).hexdigest()}",
            visibility_level=visibility_level,
            created_by=created_by,
            metadata=metadata or {},
        )
        self.records[storage_uri] = record
        self._objects[storage_uri] = encoded
        return record

    def read_json(
        self,
        storage_uri: str,
        *,
        context: RuntimeContext,
        permissions: set[str],
    ) -> dict[str, Any]:
        record = self.records[storage_uri]
        if record.tenant_id != context.tenant_id or record.project_id != context.project_id:
            self.audit_log.record(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                action="artifact.read",
                resource_type="artifact",
                resource_id=record.id,
                result="deny",
                metadata={"reason": "scope_mismatch", "visibility_level": record.visibility_level},
            )
            raise ArtifactAccessDeniedError(storage_uri)
        required_permission = f"artifact:read:{record.visibility_level}"
        if required_permission not in permissions:
            self.audit_log.record(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                action="artifact.read",
                resource_type="artifact",
                resource_id=record.id,
                result="deny",
                metadata={"visibility_level": record.visibility_level},
            )
            raise ArtifactAccessDeniedError(storage_uri)
        encoded = self._objects[storage_uri]
        checksum = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
        if checksum != record.checksum:
            self.audit_log.record(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                actor_id=context.user_id or context.service_account_id,
                actor_type="service_account" if context.service_account_id else "user",
                action="artifact.read",
                resource_type="artifact",
                resource_id=record.id,
                result="deny",
                metadata={
                    "reason": "checksum_mismatch",
                    "visibility_level": record.visibility_level,
                },
            )
            raise ArtifactChecksumMismatchError(storage_uri)
        payload = json.loads(encoded.decode("utf-8"))
        self.audit_log.record(
            tenant_id=context.tenant_id,
            project_id=context.project_id,
            actor_id=context.user_id or context.service_account_id,
            actor_type="service_account" if context.service_account_id else "user",
            action="artifact.read",
            resource_type="artifact",
            resource_id=record.id,
            result="allow",
            metadata={"visibility_level": record.visibility_level},
        )
        return dict(payload)
