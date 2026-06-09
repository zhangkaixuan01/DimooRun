import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from dimoo_run.domain.models import APIKey
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
    id: int
    tenant_id: int
    project_id: int | None
    name: str
    owner_type: str
    owner_id: int
    key_hash: str
    key_prefix: str
    scopes: set[str]
    status: str
    created_by: str
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True)
class AuthenticatedActor:
    tenant_id: int
    project_id: int | None
    actor_type: str
    actor_id: str
    scopes: frozenset[str]
    api_key_id: int | None


class APIKeyAuthenticator:
    def __init__(
        self,
        *,
        service_accounts: ServiceAccountRegistry,
        audit_sink: AuditSink | None = None,
        now: Callable[[], datetime] | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.service_accounts = service_accounts
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self._now = now or (lambda: datetime.now(UTC))
        self._session_factory = session_factory
        self.keys: dict[int, APIKeyRecord] = {}
        self._next_id = 1

    def create_key(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        name: str,
        owner_type: str,
        owner_id: int,
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
        key_prefix = plain_key[:12]
        record = APIKeyRecord(
            id=self._next_id,
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            owner_type=owner_type,
            owner_id=owner_id,
            key_hash=self._hash(plain_key),
            key_prefix=key_prefix,
            scopes=set(scopes),
            status="active",
            created_by=created_by,
            created_at=self._now(),
            expires_at=expires_at,
        )
        self._next_id += 1
        if self._session_factory is not None:
            with self._session_factory() as session:
                model = _model_from_record(record)
                session.add(model)
                session.flush()
                session.commit()
                return plain_key, _record_from_model(model)
        self.keys[record.id] = record
        return plain_key, record

    def authenticate(
        self,
        plain_key: str,
        *,
        tenant_id: int,
        project_id: int | None,
        required_scope: str,
    ) -> AuthenticatedActor:
        record = self._find_by_hash(self._hash(plain_key))
        if record.status != "active":
            raise APIKeyDisabledError(record.id)
        if record.expires_at is not None and record.expires_at <= self._now():
            raise APIKeyDisabledError(record.id)
        if record.tenant_id != tenant_id:
            raise APIKeyScopeError("tenant_scope_mismatch")
        if record.project_id is not None and (
            project_id is None or record.project_id != project_id
        ):
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
                actor_id=str(record.owner_id),
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
            actor_id=str(record.owner_id),
            scopes=frozenset(record.scopes),
            api_key_id=record.id,
        )

    def disable_key(self, key_id: int, *, actor_id: str) -> APIKeyRecord:
        if self._session_factory is not None:
            with self._session_factory() as session:
                model = session.get(APIKey, key_id)
                if model is None:
                    raise KeyError(key_id)
                model.status = "disabled"
                model.updated_by = actor_id
                model.updated_at = self._now()
                session.commit()
                session.refresh(model)
                return _record_from_model(model)
        self.keys[key_id].status = "disabled"
        return self.keys[key_id]

    def enable_key(self, key_id: int, *, actor_id: str) -> APIKeyRecord:
        if self._session_factory is not None:
            with self._session_factory() as session:
                model = session.get(APIKey, key_id)
                if model is None or model.is_deleted:
                    raise KeyError(key_id)
                record = _record_from_model(model)
                self._assert_owner_scope_subset(
                    tenant_id=record.tenant_id,
                    project_id=record.project_id,
                    owner_type=record.owner_type,
                    owner_id=record.owner_id,
                    scopes=record.scopes,
                )
                model.status = "active"
                model.updated_by = actor_id
                model.updated_at = self._now()
                session.commit()
                session.refresh(model)
                return _record_from_model(model)
        record = self.keys[key_id]
        self._assert_owner_scope_subset(
            tenant_id=record.tenant_id,
            project_id=record.project_id,
            owner_type=record.owner_type,
            owner_id=record.owner_id,
            scopes=record.scopes,
        )
        record.status = "active"
        return record

    def delete_key(self, key_id: int, *, actor_id: str) -> APIKeyRecord:
        if self._session_factory is not None:
            with self._session_factory() as session:
                model = session.get(APIKey, key_id)
                if model is None or model.is_deleted:
                    raise KeyError(key_id)
                model.status = "deleted"
                model.is_deleted = True
                model.deleted_by = actor_id
                model.deleted_at = self._now()
                model.updated_by = actor_id
                model.updated_at = model.deleted_at
                session.commit()
                session.refresh(model)
                return _record_from_model(model)
        record = self.keys.pop(key_id)
        record.status = "deleted"
        return record

    def list_keys(
        self,
        *,
        owner_type: str | None = None,
        owner_id: int | None = None,
    ) -> list[APIKeyRecord]:
        if self._session_factory is not None:
            with self._session_factory() as session:
                conditions: list[ColumnElement[bool]] = [APIKey.is_deleted.is_(False)]
                if owner_type is not None:
                    conditions.append(APIKey.owner_type == owner_type)
                if owner_id is not None:
                    conditions.append(APIKey.owner_id == owner_id)
                statement = select(APIKey).where(*conditions).order_by(APIKey.created_at.desc())
                return [_record_from_model(model) for model in session.scalars(statement)]
        records = list(self.keys.values())
        if owner_type is not None:
            records = [record for record in records if record.owner_type == owner_type]
        if owner_id is not None:
            records = [record for record in records if record.owner_id == owner_id]
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def _assert_owner_scope_subset(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        owner_type: str,
        owner_id: int,
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
        if self._session_factory is not None:
            with self._session_factory() as session:
                model = session.scalar(
                    select(APIKey).where(
                        APIKey.key_hash == key_hash,
                        APIKey.is_deleted.is_(False),
                    )
                )
                if model is None:
                    raise APIKeyError("api_key_not_found")
                record = _record_from_model(model)
                if record.status == "active":
                    model.last_used_at = self._now()
                    model.updated_at = model.last_used_at
                    session.commit()
                    record.last_used_at = model.last_used_at
                return record
        for record in self.keys.values():
            if record.key_hash == key_hash:
                return record
        raise APIKeyError("api_key_not_found")

    def _hash(self, plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()


def _model_from_record(record: APIKeyRecord) -> APIKey:
    return APIKey(
        tenant_id=record.tenant_id,
        project_id=record.project_id,
        name=record.name,
        owner_type=record.owner_type,
        owner_id=record.owner_id,
        key_hash=record.key_hash,
        key_prefix=record.key_prefix,
        scopes_json=sorted(record.scopes),
        status=record.status,
        created_by=record.created_by,
        updated_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.created_at,
        expires_at=record.expires_at,
    )


def _record_from_model(model: APIKey) -> APIKeyRecord:
    return APIKeyRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        name=model.name,
        owner_type=model.owner_type,
        owner_id=model.owner_id,
        key_hash=model.key_hash,
        key_prefix=model.key_prefix,
        scopes=set(model.scopes_json or []),
        status=model.status,
        created_by=model.created_by or "system",
        created_at=model.created_at,
        last_used_at=model.last_used_at,
        expires_at=model.expires_at,
    )
