import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import pbkdf2_hmac, sha256
from typing import Any, Protocol, cast
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    ConsoleOperator as ConsoleOperatorModel,
)
from dimoo_run.domain.models import (
    ConsoleOperatorAllowedScope as ConsoleOperatorAllowedScopeModel,
)
from dimoo_run.domain.models import (
    ConsoleOperatorCredential,
    ConsoleOperatorPermission,
    ConsoleOperatorRole,
    ConsolePermission,
    ConsoleRole,
    ConsoleRolePermission,
)
from dimoo_run.domain.models import (
    ConsoleOperatorSession as ConsoleOperatorSessionModel,
)
from dimoo_run.persistence.database import Base, create_session_factory


class ConsoleIdentityUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConsoleOperator:
    id: str
    email: str
    name: str
    roles: list[str]
    permissions: set[str]
    allowed_scopes: list[dict[str, str]]
    status: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    password_changed_at: datetime | None = None


@dataclass(frozen=True)
class ConsoleSession:
    token: str
    operator_id: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class ConsoleOperatorSessionRecord:
    id: str
    operator_id: str
    status: str
    last_used_at: datetime
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None
    ip_address: str | None
    user_agent: str | None


class SessionCache(Protocol):
    def get(self, token_hash: str) -> dict[str, Any] | None: ...
    def set(self, token_hash: str, payload: dict[str, Any], ttl_seconds: int) -> None: ...
    def delete(self, token_hash: str) -> None: ...
    def clear(self) -> None: ...


class RedisSessionCache:
    def __init__(self, url: str) -> None:
        self._client: Redis = Redis.from_url(url, decode_responses=True)

    def get(self, token_hash: str) -> dict[str, Any] | None:
        try:
            raw = self._client.get(_session_cache_key(token_hash))
        except RedisError as exc:
            raise ConsoleIdentityUnavailableError("redis_unavailable") from exc
        if raw is None:
            return None
        return cast(dict[str, Any], json.loads(str(raw)))

    def set(self, token_hash: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        try:
            self._client.setex(_session_cache_key(token_hash), ttl_seconds, json.dumps(payload))
        except RedisError as exc:
            raise ConsoleIdentityUnavailableError("redis_unavailable") from exc

    def delete(self, token_hash: str) -> None:
        try:
            self._client.delete(_session_cache_key(token_hash))
        except RedisError as exc:
            raise ConsoleIdentityUnavailableError("redis_unavailable") from exc

    def clear(self) -> None:
        try:
            for key in self._client.scan_iter("console:session:*"):
                self._client.delete(key)
        except RedisError as exc:
            raise ConsoleIdentityUnavailableError("redis_unavailable") from exc


class MemorySessionCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[dict[str, Any], datetime]] = {}

    def get(self, token_hash: str) -> dict[str, Any] | None:
        item = self._items.get(token_hash)
        if item is None:
            return None
        payload, expires_at = item
        if expires_at <= _now():
            self._items.pop(token_hash, None)
            return None
        return dict(payload)

    def set(self, token_hash: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        self._items[token_hash] = (dict(payload), _now() + timedelta(seconds=ttl_seconds))

    def delete(self, token_hash: str) -> None:
        self._items.pop(token_hash, None)

    def clear(self) -> None:
        self._items.clear()


class ConsoleIdentityService:
    def __init__(self, session_factory: sessionmaker[Session], cache: SessionCache) -> None:
        self._session_factory = session_factory
        self._cache = cache

    def reset(self) -> None:
        self._ensure_tables()
        with self._session_factory() as session:
            for model in [
                ConsoleOperatorPermission,
                ConsoleRolePermission,
                ConsoleOperatorRole,
                ConsoleOperatorAllowedScopeModel,
                ConsoleOperatorSessionModel,
                ConsoleOperatorCredential,
                ConsolePermission,
                ConsoleRole,
                ConsoleOperatorModel,
            ]:
                session.execute(delete(model))
            session.commit()
        self._cache.clear()

    def ensure_bootstrap_operator(self) -> ConsoleOperator:
        self._ensure_tables()
        email = os.getenv("DIMOORUN_BOOTSTRAP_ADMIN_EMAIL", "admin@local.dimoorun")
        password = os.getenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", "admin123")
        name = os.getenv("DIMOORUN_BOOTSTRAP_ADMIN_NAME", "Bootstrap Admin")
        with self._session_factory() as session:
            self._seed_builtin_permissions(session)
            existing = self._operator_by_email(session, email)
            if existing is not None:
                return self._hydrate_operator(session, existing)
            now = _now()
            operator = ConsoleOperatorModel(
                id="operator_bootstrap_admin",
                email=email,
                name=name,
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(operator)
            session.add(
                ConsoleOperatorCredential(
                    id=_id("credential"),
                    operator_id=operator.id,
                    password_hash=hash_password(password),
                    password_changed_at=now,
                    failed_login_count=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._replace_operator_roles(session, operator.id, ["platform_admin"])
            self._replace_operator_permissions(session, operator.id, {"*"})
            self._replace_operator_scopes(session, operator.id, [_default_scope()])
            session.commit()
            return self._hydrate_operator(session, operator)

    def authenticate(
        self,
        email: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ConsoleSession | None:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = self._operator_by_email(session, email)
            if operator is None or operator.status != "active" or operator.is_deleted:
                return None
            credential = session.scalar(
                select(ConsoleOperatorCredential).where(
                    ConsoleOperatorCredential.operator_id == operator.id
                )
            )
            if credential is None:
                return None
            now = _now()
            if credential.locked_until is not None and _as_utc(credential.locked_until) > now:
                return None
            if not verify_password(password, credential.password_hash):
                credential.failed_login_count += 1
                if credential.failed_login_count >= 5:
                    credential.locked_until = now + timedelta(minutes=15)
                session.commit()
                return None
            token = f"sess_{secrets.token_urlsafe(32)}"
            token_hash = hash_token(token)
            expires_at = now + timedelta(seconds=_session_ttl_seconds())
            session_model = ConsoleOperatorSessionModel(
                id=_id("session"),
                operator_id=operator.id,
                token_hash=token_hash,
                last_used_at=now,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                created_at=now,
                updated_at=now,
            )
            credential.failed_login_count = 0
            credential.locked_until = None
            operator.last_login_at = now
            operator.updated_at = now
            session.add(session_model)
            payload = self._session_cache_payload(session, session_model, operator)
            self._cache.set(token_hash, payload, max(1, int((expires_at - now).total_seconds())))
            session.commit()
            return ConsoleSession(
                token=token,
                operator_id=operator.id,
                created_at=now,
                last_used_at=now,
                expires_at=expires_at,
            )

    def get_operator_by_session(self, token: str) -> ConsoleOperator | None:
        token_hash = hash_token(token)
        cached = self._cache.get(token_hash)
        if cached is not None:
            expires_at = _parse_datetime(str(cached["expires_at"]))
            if expires_at <= _now():
                self.revoke_session(token, reason="expired")
                return None
            with self._session_factory() as session:
                session_model = session.scalar(
                    select(ConsoleOperatorSessionModel).where(
                        ConsoleOperatorSessionModel.token_hash == token_hash
                    )
                )
                if not self._session_is_active(session_model):
                    self._cache.delete(token_hash)
                    return None
                assert session_model is not None
                operator = session.get(ConsoleOperatorModel, str(cached["operator_id"]))
                if operator is None or operator.status != "active" or operator.is_deleted:
                    self._cache.delete(token_hash)
                    return None
                session_model.last_used_at = _now()
                session.commit()
                return self._hydrate_operator(session, operator)
        return self._get_operator_by_session_from_db(token_hash)

    def revoke_session(self, token: str, *, reason: str = "logout") -> None:
        token_hash = hash_token(token)
        with self._session_factory() as session:
            session_model = session.scalar(
                select(ConsoleOperatorSessionModel).where(
                    ConsoleOperatorSessionModel.token_hash == token_hash
                )
            )
            if session_model is not None and session_model.revoked_at is None:
                session_model.revoked_at = _now()
                session_model.revoke_reason = reason
                session.commit()
        self._cache.delete(token_hash)

    def list_operators(self) -> list[ConsoleOperator]:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operators = list(
                session.scalars(
                    select(ConsoleOperatorModel)
                    .where(ConsoleOperatorModel.is_deleted.is_(False))
                    .order_by(ConsoleOperatorModel.created_at)
                )
            )
            return [self._hydrate_operator(session, operator) for operator in operators]

    def create_operator(
        self,
        *,
        email: str,
        name: str,
        password: str,
        roles: list[str] | None = None,
        permissions: set[str] | None = None,
        allowed_scopes: list[dict[str, str]] | None = None,
    ) -> ConsoleOperator:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            if self._operator_by_email(session, email) is not None:
                raise ValueError("operator_email_exists")
            now = _now()
            operator = ConsoleOperatorModel(
                id=_id("operator"),
                email=email,
                name=name,
                status="active",
                created_at=now,
                updated_at=now,
            )
            session.add(operator)
            session.add(
                ConsoleOperatorCredential(
                    id=_id("credential"),
                    operator_id=operator.id,
                    password_hash=hash_password(password),
                    password_changed_at=now,
                    failed_login_count=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._replace_operator_roles(session, operator.id, roles or ["runtime_operator"])
            self._replace_operator_permissions(
                session, operator.id, permissions or {"agent:read", "run:read"}
            )
            self._replace_operator_scopes(
                session,
                operator.id,
                allowed_scopes or [_default_scope()],
            )
            session.commit()
            return self._hydrate_operator(session, operator)

    def update_operator(
        self,
        operator_id: str,
        *,
        name: str | None = None,
        roles: list[str] | None = None,
        permissions: set[str] | None = None,
        allowed_scopes: list[dict[str, str]] | None = None,
        status: str | None = None,
    ) -> ConsoleOperator | None:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = session.get(ConsoleOperatorModel, operator_id)
            if operator is None or operator.is_deleted:
                return None
            if name is not None:
                operator.name = name
            if status is not None:
                operator.status = status
                if status != "active":
                    self._revoke_operator_sessions(session, operator_id, reason="operator_disabled")
            if roles is not None:
                self._replace_operator_roles(session, operator_id, roles)
            if permissions is not None:
                self._replace_operator_permissions(session, operator_id, permissions)
            if allowed_scopes is not None:
                self._replace_operator_scopes(session, operator_id, allowed_scopes)
            operator.updated_at = _now()
            session.commit()
            return self._hydrate_operator(session, operator)

    def change_password(
        self,
        operator_id: str,
        *,
        current_password: str | None,
        new_password: str,
        require_current: bool = True,
    ) -> bool:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = session.get(ConsoleOperatorModel, operator_id)
            if operator is None or operator.is_deleted:
                return False
            credential = session.scalar(
                select(ConsoleOperatorCredential).where(
                    ConsoleOperatorCredential.operator_id == operator_id
                )
            )
            if credential is None:
                return False
            if require_current and (
                current_password is None
                or not verify_password(current_password, credential.password_hash)
            ):
                return False
            now = _now()
            credential.password_hash = hash_password(new_password)
            credential.password_changed_at = now
            credential.updated_at = now
            operator.updated_at = now
            self._revoke_operator_sessions(session, operator_id, reason="password_changed")
            session.commit()
            return True

    def revoke_operator_sessions(self, operator_id: str, *, reason: str = "admin_revoked") -> bool:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = session.get(ConsoleOperatorModel, operator_id)
            if operator is None or operator.is_deleted:
                return False
            self._revoke_operator_sessions(session, operator_id, reason=reason)
            operator.updated_at = _now()
            session.commit()
            return True

    def list_operator_sessions(self, operator_id: str) -> list[ConsoleOperatorSessionRecord] | None:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = session.get(ConsoleOperatorModel, operator_id)
            if operator is None or operator.is_deleted:
                return None
            rows = list(
                session.scalars(
                    select(ConsoleOperatorSessionModel)
                    .where(ConsoleOperatorSessionModel.operator_id == operator_id)
                    .order_by(ConsoleOperatorSessionModel.created_at.desc())
                )
            )
            return [self._hydrate_session_record(row) for row in rows]

    def delete_operator(self, operator_id: str) -> ConsoleOperator | None:
        self.ensure_bootstrap_operator()
        with self._session_factory() as session:
            operator = session.get(ConsoleOperatorModel, operator_id)
            if operator is None or operator.is_deleted:
                return None
            now = _now()
            operator.status = "deleted"
            operator.is_deleted = True
            operator.deleted_at = now
            operator.updated_at = now
            self._revoke_operator_sessions(session, operator_id, reason="operator_deleted")
            hydrated = self._hydrate_operator(session, operator)
            session.commit()
            return hydrated

    def can_access_scope(
        self,
        operator: ConsoleOperator,
        tenant_id: str,
        project_id: str | None,
        environment: str | None,
    ) -> bool:
        for scope in operator.allowed_scopes:
            tenant_ok = scope.get("tenant_id") in {"*", tenant_id}
            project_ok = project_id is None or scope.get("project_id") in {"*", project_id}
            environment_ok = environment is None or scope.get("environment") in {"*", environment}
            if tenant_ok and project_ok and environment_ok:
                return True
        return False

    def _get_operator_by_session_from_db(self, token_hash: str) -> ConsoleOperator | None:
        with self._session_factory() as session:
            session_model = session.scalar(
                select(ConsoleOperatorSessionModel).where(
                    ConsoleOperatorSessionModel.token_hash == token_hash
                )
            )
            if not self._session_is_active(session_model):
                if session_model is not None:
                    self._cache.delete(token_hash)
                return None
            assert session_model is not None
            operator = session.get(ConsoleOperatorModel, session_model.operator_id)
            if operator is None or operator.status != "active" or operator.is_deleted:
                self._cache.delete(token_hash)
                return None
            now = _now()
            session_model.last_used_at = now
            payload = self._session_cache_payload(session, session_model, operator)
            self._cache.set(
                token_hash,
                payload,
                max(1, int((_as_utc(session_model.expires_at) - now).total_seconds())),
            )
            session.commit()
            return self._hydrate_operator(session, operator)

    def _session_is_active(self, session_model: ConsoleOperatorSessionModel | None) -> bool:
        if session_model is None:
            return False
        if session_model.revoked_at is not None:
            return False
        if _as_utc(session_model.expires_at) <= _now():
            return False
        return True

    def _hydrate_session_record(
        self,
        session_model: ConsoleOperatorSessionModel,
    ) -> ConsoleOperatorSessionRecord:
        expires_at = _as_utc(session_model.expires_at)
        revoked_at = _as_utc(session_model.revoked_at) if session_model.revoked_at else None
        status = "revoked" if revoked_at is not None else "expired" if expires_at <= _now() else "active"
        return ConsoleOperatorSessionRecord(
            id=session_model.id,
            operator_id=session_model.operator_id,
            status=status,
            last_used_at=_as_utc(session_model.last_used_at),
            expires_at=expires_at,
            created_at=_as_utc(session_model.created_at),
            updated_at=_as_utc(session_model.updated_at or session_model.created_at),
            revoked_at=revoked_at,
            revoke_reason=session_model.revoke_reason,
            ip_address=session_model.ip_address,
            user_agent=session_model.user_agent,
        )

    def _operator_by_email(self, session: Session, email: str) -> ConsoleOperatorModel | None:
        return session.scalar(
            select(ConsoleOperatorModel).where(
                ConsoleOperatorModel.email == email,
                ConsoleOperatorModel.is_deleted.is_(False),
            )
        )

    def _hydrate_operator(
        self,
        session: Session,
        operator: ConsoleOperatorModel,
    ) -> ConsoleOperator:
        roles = self._operator_roles(session, operator.id)
        permissions = self._operator_permissions(session, operator.id)
        scopes = [
            {
                "tenant_id": scope.tenant_id,
                "project_id": scope.project_id,
                "environment": scope.environment,
            }
            for scope in session.scalars(
                select(ConsoleOperatorAllowedScopeModel)
                .where(
                    ConsoleOperatorAllowedScopeModel.operator_id == operator.id,
                    ConsoleOperatorAllowedScopeModel.is_deleted.is_(False),
                )
                .order_by(ConsoleOperatorAllowedScopeModel.created_at)
            )
        ]
        credential = session.scalar(
            select(ConsoleOperatorCredential).where(
                ConsoleOperatorCredential.operator_id == operator.id
            )
        )
        return ConsoleOperator(
            id=operator.id,
            email=operator.email,
            name=operator.name,
            roles=roles,
            permissions=permissions,
            allowed_scopes=scopes,
            status=operator.status,
            created_at=_as_utc(operator.created_at),
            updated_at=_as_utc(operator.updated_at or operator.created_at),
            last_login_at=_as_utc(operator.last_login_at) if operator.last_login_at else None,
            password_changed_at=(
                _as_utc(credential.password_changed_at)
                if credential and credential.password_changed_at
                else None
            ),
        )

    def _operator_roles(self, session: Session, operator_id: str) -> list[str]:
        statement = (
            select(ConsoleRole.name)
            .join(ConsoleOperatorRole, ConsoleOperatorRole.role_id == ConsoleRole.id)
            .where(
                ConsoleOperatorRole.operator_id == operator_id,
                ConsoleOperatorRole.is_deleted.is_(False),
                ConsoleRole.is_deleted.is_(False),
                ConsoleRole.status == "active",
            )
            .order_by(ConsoleRole.name)
        )
        return list(session.scalars(statement))

    def _operator_permissions(self, session: Session, operator_id: str) -> set[str]:
        direct = set(
            session.scalars(
                select(ConsolePermission.code)
                .join(
                    ConsoleOperatorPermission,
                    ConsoleOperatorPermission.permission_id == ConsolePermission.id,
                )
                .where(
                    ConsoleOperatorPermission.operator_id == operator_id,
                    ConsoleOperatorPermission.is_deleted.is_(False),
                    ConsolePermission.is_deleted.is_(False),
                    ConsolePermission.status == "active",
                )
            )
        )
        via_roles = set(
            session.scalars(
                select(ConsolePermission.code)
                .join(
                    ConsoleRolePermission,
                    ConsoleRolePermission.permission_id == ConsolePermission.id,
                )
                .join(
                    ConsoleOperatorRole,
                    ConsoleOperatorRole.role_id == ConsoleRolePermission.role_id,
                )
                .where(
                    ConsoleOperatorRole.operator_id == operator_id,
                    ConsoleOperatorRole.is_deleted.is_(False),
                    ConsoleRolePermission.is_deleted.is_(False),
                    ConsolePermission.is_deleted.is_(False),
                    ConsolePermission.status == "active",
                )
            )
        )
        return direct | via_roles

    def _replace_operator_roles(self, session: Session, operator_id: str, roles: list[str]) -> None:
        session.execute(
            delete(ConsoleOperatorRole).where(ConsoleOperatorRole.operator_id == operator_id)
        )
        for role_name in roles:
            role = self._ensure_role(session, role_name)
            session.add(
                ConsoleOperatorRole(
                    id=_id("operator_role"),
                    operator_id=operator_id,
                    role_id=role.id,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )

    def _replace_operator_permissions(
        self, session: Session, operator_id: str, permissions: set[str]
    ) -> None:
        session.execute(
            delete(ConsoleOperatorPermission).where(
                ConsoleOperatorPermission.operator_id == operator_id
            )
        )
        for permission_code in permissions:
            permission = self._ensure_permission(session, permission_code)
            session.add(
                ConsoleOperatorPermission(
                    id=_id("operator_permission"),
                    operator_id=operator_id,
                    permission_id=permission.id,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )

    def _replace_operator_scopes(
        self, session: Session, operator_id: str, scopes: list[dict[str, str]]
    ) -> None:
        session.execute(
            delete(ConsoleOperatorAllowedScopeModel).where(
                ConsoleOperatorAllowedScopeModel.operator_id == operator_id
            )
        )
        for scope in scopes:
            session.add(
                ConsoleOperatorAllowedScopeModel(
                    id=_id("operator_scope"),
                    operator_id=operator_id,
                    tenant_id=str(scope.get("tenant_id") or "*"),
                    project_id=str(scope.get("project_id") or "*"),
                    environment=str(scope.get("environment") or "*"),
                    created_at=_now(),
                    updated_at=_now(),
                )
            )

    def _revoke_operator_sessions(self, session: Session, operator_id: str, *, reason: str) -> None:
        now = _now()
        sessions = list(
            session.scalars(
                select(ConsoleOperatorSessionModel).where(
                    ConsoleOperatorSessionModel.operator_id == operator_id,
                    ConsoleOperatorSessionModel.revoked_at.is_(None),
                )
            )
        )
        for session_model in sessions:
            session_model.revoked_at = now
            session_model.revoke_reason = reason
            self._cache.delete(session_model.token_hash)

    def _session_cache_payload(
        self,
        session: Session,
        session_model: ConsoleOperatorSessionModel,
        operator: ConsoleOperatorModel,
    ) -> dict[str, Any]:
        hydrated = self._hydrate_operator(session, operator)
        return {
            "session_id": session_model.id,
            "operator_id": operator.id,
            "roles": hydrated.roles,
            "permissions": sorted(hydrated.permissions),
            "allowed_scopes": hydrated.allowed_scopes,
            "expires_at": _as_utc(session_model.expires_at).isoformat(),
        }

    def _seed_builtin_permissions(self, session: Session) -> None:
        role_permissions = {
            "platform_admin": ["*"],
            "runtime_operator": ["agent:read", "run:read"],
            "identity_admin": [
                "admin:read",
                "identity:operator:write",
                "identity:role:write",
                "identity:permission:write",
                "identity:scope:write",
                "identity:service-account:write",
                "identity:api-key:write",
            ],
        }
        for role_name, permission_codes in role_permissions.items():
            role = self._ensure_role(session, role_name)
            session.execute(
                delete(ConsoleRolePermission).where(ConsoleRolePermission.role_id == role.id)
            )
            for code in permission_codes:
                permission = self._ensure_permission(session, code)
                session.add(
                    ConsoleRolePermission(
                        id=_id("role_permission"),
                        role_id=role.id,
                        permission_id=permission.id,
                        created_at=_now(),
                        updated_at=_now(),
                    )
                )

    def _ensure_role(self, session: Session, role_name: str) -> ConsoleRole:
        role = session.scalar(select(ConsoleRole).where(ConsoleRole.name == role_name))
        if role is not None:
            return role
        role = ConsoleRole(
            id=_id("role"),
            name=role_name,
            description=None,
            status="active",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(role)
        session.flush()
        return role

    def _ensure_permission(self, session: Session, code: str) -> ConsolePermission:
        permission = session.scalar(select(ConsolePermission).where(ConsolePermission.code == code))
        if permission is not None:
            return permission
        resource, action = _permission_parts(code)
        permission = ConsolePermission(
            id=_id("permission"),
            code=code,
            resource=resource,
            action=action,
            description=None,
            status="active",
            created_at=_now(),
            updated_at=_now(),
        )
        session.add(permission)
        session.flush()
        return permission

    def _ensure_tables(self) -> None:
        settings = Settings.from_env()
        if settings.runtime.mode == "dev":
            with self._session_factory() as session:
                Base.metadata.create_all(session.get_bind())


def console_operator_to_public(operator: ConsoleOperator) -> dict[str, Any]:
    return {
        "id": operator.id,
        "email": operator.email,
        "name": operator.name,
        "roles": operator.roles,
        "permissions": sorted(operator.permissions),
        "allowed_scopes": operator.allowed_scopes,
        "status": operator.status,
        "created_at": operator.created_at.isoformat(),
        "updated_at": operator.updated_at.isoformat(),
        "last_login_at": operator.last_login_at.isoformat() if operator.last_login_at else None,
        "password_changed_at": (
            operator.password_changed_at.isoformat() if operator.password_changed_at else None
        ),
    }


def console_operator_session_to_public(session: ConsoleOperatorSessionRecord) -> dict[str, Any]:
    return {
        "id": session.id,
        "operator_id": session.operator_id,
        "status": session.status,
        "last_used_at": session.last_used_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "revoke_reason": session.revoke_reason,
        "ip_address": session.ip_address,
        "user_agent": session.user_agent,
    }


@lru_cache(maxsize=1)
def default_console_identity_service() -> ConsoleIdentityService:
    settings = Settings.from_env()
    return ConsoleIdentityService(
        session_factory=_session_factory(settings.database.url),
        cache=_session_cache(settings.redis.url),
    )


def reset_default_console_identity_service() -> None:
    default_console_identity_service.cache_clear()


@lru_cache(maxsize=4)
def _session_factory(database_url: str) -> sessionmaker[Session]:
    return create_session_factory(database_url)


@lru_cache(maxsize=4)
def _session_cache(redis_url: str) -> SessionCache:
    if redis_url.startswith("memory://"):
        return MemorySessionCache()
    return RedisSessionCache(redis_url)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 240_000
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        )
        return secrets.compare_digest(digest.hex(), expected)
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _session_cache_key(token_hash: str) -> str:
    return f"console:session:{token_hash}"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_datetime(value: str) -> datetime:
    return _as_utc(datetime.fromisoformat(value))


def _session_ttl_seconds() -> int:
    return int(os.getenv("DIMOORUN_CONSOLE_ACCESS_TOKEN_TTL_SECONDS", str(12 * 60 * 60)))


def _default_scope() -> dict[str, str]:
    return {
        "tenant_id": os.getenv("DIMOORUN_DEFAULT_TENANT_ID", "tenant_1"),
        "project_id": os.getenv("DIMOORUN_DEFAULT_PROJECT_ID", "project_1"),
        "environment": os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local"),
    }


def _permission_parts(code: str) -> tuple[str, str]:
    if code == "*":
        return "*", "*"
    if ":" in code:
        resource, action = code.rsplit(":", 1)
        return resource, action
    return code, "use"
