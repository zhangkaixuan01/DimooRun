import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from dimoo_run.core.context import RuntimeContext
from dimoo_run.observability.audit import InMemoryComplianceAuditLog


class ArtifactAccessDeniedError(PermissionError):
    error_code = "artifact_access_denied"


class ArtifactChecksumMismatchError(RuntimeError):
    error_code = "artifact_checksum_mismatch"


@dataclass(frozen=True)
class ArtifactRecord:
    id: int
    tenant_id: int
    project_id: int | None
    run_id: int | None
    attempt_id: int | None
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


class ObjectStoreClient(Protocol):
    def put_object(
        self,
        *,
        bucket: str,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
    ) -> None: ...

    def get_object(self, *, bucket: str, key: str) -> bytes: ...

    def presigned_get_url(self, *, bucket: str, key: str, expires_seconds: int) -> str: ...


def _checksum(encoded: bytes) -> str:
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _encode_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _ensure_checksum(storage_uri: str, encoded: bytes, expected: str) -> None:
    if _checksum(encoded) != expected:
        raise ArtifactChecksumMismatchError(storage_uri)


class InMemoryArtifactStore:
    def __init__(self, *, audit_log: InMemoryComplianceAuditLog) -> None:
        self.audit_log = audit_log
        self.records: dict[str, ArtifactRecord] = {}
        self._objects: dict[str, bytes] = {}
        self._next_id = 1

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
        encoded = _encode_json(payload)
        artifact_id = self._allocate_id()
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
            checksum=_checksum(encoded),
            visibility_level=visibility_level,
            created_by=created_by,
            metadata=metadata or {},
        )
        self.records[storage_uri] = record
        self._objects[storage_uri] = encoded
        return record

    def _allocate_id(self) -> int:
        artifact_id = self._next_id
        self._next_id += 1
        return artifact_id

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
        if _checksum(encoded) != record.checksum:
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


class LocalArtifactStore(InMemoryArtifactStore):
    def __init__(
        self,
        *,
        audit_log: InMemoryComplianceAuditLog,
        root: str | Path,
        public_base_url: str | None = None,
    ) -> None:
        super().__init__(audit_log=audit_log)
        self.root = Path(root)
        self.objects_root = self.root / "objects"
        self.metadata_root = self.root / "metadata"
        self.public_base_url = public_base_url
        self.objects_root.mkdir(parents=True, exist_ok=True)
        self.metadata_root.mkdir(parents=True, exist_ok=True)

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
        encoded = _encode_json(payload)
        artifact_id = self._allocate_id()
        object_path = self.objects_root / f"{artifact_id}.json"
        metadata_path = self.metadata_root / f"{artifact_id}.json"
        storage_uri = f"local://artifact/{artifact_id}"
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
            checksum=_checksum(encoded),
            visibility_level=visibility_level,
            created_by=created_by,
            metadata=metadata or {},
        )
        object_path.write_bytes(encoded)
        metadata_path.write_text(
            json.dumps(_record_to_json(record), separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        self.records[storage_uri] = record
        return record

    def read_json(
        self,
        storage_uri: str,
        *,
        context: RuntimeContext,
        permissions: set[str],
    ) -> dict[str, Any]:
        record = self.records[storage_uri]
        self._authorize_read(record, context=context, permissions=permissions)
        encoded = (self.objects_root / f"{record.id}.json").read_bytes()
        try:
            _ensure_checksum(storage_uri, encoded, record.checksum)
        except ArtifactChecksumMismatchError:
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
            raise
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
        payload = json.loads(encoded.decode("utf-8"))
        return dict(payload)

    def signed_download_url(self, storage_uri: str, *, expires_seconds: int = 300) -> str:
        record = self.records[storage_uri]
        if self.public_base_url:
            base_url = self.public_base_url.rstrip("/")
            return f"{base_url}/{quote(str(record.id))}?expires={expires_seconds}"
        return f"{storage_uri}?expires={expires_seconds}"

    def _authorize_read(
        self,
        record: ArtifactRecord,
        *,
        context: RuntimeContext,
        permissions: set[str],
    ) -> None:
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
            raise ArtifactAccessDeniedError(record.storage_uri)
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
            raise ArtifactAccessDeniedError(record.storage_uri)


class S3CompatibleArtifactStore(LocalArtifactStore):
    def __init__(
        self,
        *,
        audit_log: InMemoryComplianceAuditLog,
        bucket: str,
        endpoint_url: str,
        root: str | Path,
        scheme: str = "s3",
        object_client: ObjectStoreClient | None = None,
    ) -> None:
        super().__init__(audit_log=audit_log, root=root, public_base_url=endpoint_url)
        self.bucket = bucket
        self.endpoint_url = endpoint_url.rstrip("/")
        self.scheme = scheme
        self.object_client = object_client

    def write_json(self, **kwargs: Any) -> ArtifactRecord:
        record = super().write_json(**kwargs)
        storage_uri = f"{self.scheme}://{self.bucket}/artifacts/{record.id}.json"
        s3_record = replace(record, storage_uri=storage_uri)
        self.records.pop(record.storage_uri)
        self.records[storage_uri] = s3_record
        metadata_path = self.metadata_root / f"{record.id}.json"
        metadata_path.write_text(
            json.dumps(_record_to_json(s3_record), separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        if self.object_client is not None:
            object_path = self.objects_root / f"{record.id}.json"
            self.object_client.put_object(
                bucket=self.bucket,
                key=_object_key(record.id),
                body=object_path.read_bytes(),
                content_type=record.mime_type,
                metadata={"checksum": record.checksum, "artifact_id": str(record.id)},
            )
        return s3_record

    def read_json(
        self,
        storage_uri: str,
        *,
        context: RuntimeContext,
        permissions: set[str],
    ) -> dict[str, Any]:
        if self.object_client is None:
            return super().read_json(storage_uri, context=context, permissions=permissions)
        record = self.records[storage_uri]
        self._authorize_read(record, context=context, permissions=permissions)
        encoded = self.object_client.get_object(bucket=self.bucket, key=_object_key(record.id))
        try:
            _ensure_checksum(storage_uri, encoded, record.checksum)
        except ArtifactChecksumMismatchError:
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
            raise
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
        payload = json.loads(encoded.decode("utf-8"))
        return dict(payload)

    def signed_download_url(self, storage_uri: str, *, expires_seconds: int = 300) -> str:
        record = self.records[storage_uri]
        if self.object_client is not None:
            return self.object_client.presigned_get_url(
                bucket=self.bucket,
                key=_object_key(record.id),
                expires_seconds=expires_seconds,
            )
        return (
            f"{self.endpoint_url}/{quote(self.bucket)}/artifacts/{quote(str(record.id))}.json"
            f"?expires={expires_seconds}"
        )


def _record_to_json(record: ArtifactRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "tenant_id": record.tenant_id,
        "project_id": record.project_id,
        "run_id": record.run_id,
        "attempt_id": record.attempt_id,
        "event_id": record.event_id,
        "artifact_type": record.artifact_type,
        "mime_type": record.mime_type,
        "size_bytes": record.size_bytes,
        "storage_uri": record.storage_uri,
        "checksum": record.checksum,
        "visibility_level": record.visibility_level,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat(),
        "metadata": record.metadata,
    }


def _object_key(artifact_id: int) -> str:
    return f"artifacts/{artifact_id}.json"
