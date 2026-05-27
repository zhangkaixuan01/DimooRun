import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from dimoo_run.identity.service_accounts import ServiceAccountRegistry
from dimoo_run.policy.engine import AuditRecord, AuditSink, InMemoryAuditSink


class APIKeyError(PermissionError):
    error_code = "api_key_invalid"


class APIKeyDisabledError(APIKeyError):
    error_code = "api_key_disabled"


class APIKeyScopeError(APIKeyError):
    error_code = "api_key_scope_denied"


@dataclass
class APIKeyRecord:
    id: str
    tenant_id: str
    project_id: str | None
    name: str
    owner_type: str
    owner_id: str
    key_hash: str
    scopes: set[str]
    status: str
    created_by: str
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class AuthenticatedActor:
    tenant_id: str
    project_id: str | None
    actor_type: str
    actor_id: str
    scopes: frozenset[str]
    api_key_id: str


class APIKeyAuthenticator:
    def __init__(
        self,
        *,
        service_accounts: ServiceAccountRegistry,
        audit_sink: AuditSink | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.service_accounts = service_accounts
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self._now = now or (lambda: datetime.now(UTC))
        self.keys: dict[str, APIKeyRecord] = {}

    def create_key(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        owner_type: str,
        owner_id: str,
        scopes: set[str],
        created_by: str,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIKeyRecord]:
        self._assert_owner_scope_subset(
            tenant_id=tenant_id,
            project_id=project_id,
            owner_type=owner_type,
            owner_id=owner_id,
            scopes=scopes,
        )
        plain_key = f"dr_{secrets.token_urlsafe(24)}"
        record = APIKeyRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            owner_type=owner_type,
            owner_id=owner_id,
            key_hash=self._hash(plain_key),
            scopes=set(scopes),
            status="active",
            created_by=created_by,
            created_at=self._now(),
            expires_at=expires_at,
        )
        self.keys[record.id] = record
        return plain_key, record

    def authenticate(
        self,
        plain_key: str,
        *,
        tenant_id: str,
        project_id: str | None,
        required_scope: str,
    ) -> AuthenticatedActor:
        record = self._find_by_hash(self._hash(plain_key))
        if record.status != "active":
            raise APIKeyDisabledError(record.id)
        if record.expires_at is not None and record.expires_at <= self._now():
            raise APIKeyDisabledError(record.id)
        if record.tenant_id != tenant_id:
            raise APIKeyScopeError("tenant_scope_mismatch")
        if record.project_id is not None and record.project_id != project_id:
            raise APIKeyScopeError("project_scope_mismatch")
        if required_scope not in record.scopes:
            raise APIKeyScopeError(required_scope)
        record.last_used_at = self._now()
        if record.owner_type == "service_account":
            self.service_accounts.mark_used(record.owner_id)
        self.audit_sink.write(
            AuditRecord(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=record.owner_id,
                actor_type=record.owner_type,
                resource_type="api_key",
                resource_id=record.id,
                action="authenticate",
                result="allow",
                metadata={"required_scope": required_scope},
            )
        )
        return AuthenticatedActor(
            tenant_id=tenant_id,
            project_id=project_id,
            actor_type=record.owner_type,
            actor_id=record.owner_id,
            scopes=frozenset(record.scopes),
            api_key_id=record.id,
        )

    def disable_key(self, key_id: str, *, actor_id: str) -> None:
        _ = actor_id
        self.keys[key_id].status = "disabled"

    def list_keys(
        self,
        *,
        owner_type: str | None = None,
        owner_id: str | None = None,
    ) -> list[APIKeyRecord]:
        records = list(self.keys.values())
        if owner_type is not None:
            records = [record for record in records if record.owner_type == owner_type]
        if owner_id is not None:
            records = [record for record in records if record.owner_id == owner_id]
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def _assert_owner_scope_subset(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        owner_type: str,
        owner_id: str,
        scopes: set[str],
    ) -> None:
        if owner_type != "service_account":
            return
        owner = self.service_accounts.get(owner_id)
        if owner.status != "active":
            raise APIKeyDisabledError("owner_disabled")
        if owner.tenant_id != tenant_id or owner.project_id != project_id:
            raise APIKeyScopeError("owner_scope_mismatch")
        owner_permissions = owner.permissions
        if not scopes <= owner_permissions:
            raise APIKeyScopeError("api_key_scope_exceeds_owner")

    def _find_by_hash(self, key_hash: str) -> APIKeyRecord:
        for record in self.keys.values():
            if record.key_hash == key_hash:
                return record
        raise APIKeyError("api_key_not_found")

    def _hash(self, plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()
