from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.domain.models import Project, ServiceAccount, Tenant


@dataclass
class ServiceAccountRecord:
    id: int
    tenant_id: int
    project_id: int | None
    name: str
    permissions: set[str]
    created_by: str
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None


class ServiceAccountRegistry:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self.service_accounts: dict[int, ServiceAccountRecord] = {}
        self._next_id = 1

    def create(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        name: str,
        permissions: set[str],
        created_by: str,
    ) -> ServiceAccountRecord:
        record = ServiceAccountRecord(
            id=self._next_id,
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            permissions=set(permissions),
            created_by=created_by,
            created_at=self._now(),
        )
        self._next_id += 1
        self.service_accounts[record.id] = record
        return record

    def get(self, service_account_id: int) -> ServiceAccountRecord:
        return self.service_accounts[service_account_id]

    def list(self) -> list[ServiceAccountRecord]:
        return sorted(
            self.service_accounts.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def set_status(self, service_account_id: int, status: str) -> ServiceAccountRecord:
        record = self.get(service_account_id)
        record.status = status
        return record

    def update(
        self,
        service_account_id: int,
        *,
        name: str | None = None,
        permissions: set[str] | None = None,
        status: str | None = None,
    ) -> ServiceAccountRecord:
        record = self.get(service_account_id)
        if name is not None:
            record.name = name
        if permissions is not None:
            record.permissions = set(permissions)
        if status is not None:
            record.status = status
        return record

    def delete(self, service_account_id: int) -> ServiceAccountRecord:
        record = self.get(service_account_id)
        record.status = "deleted"
        return record

    def mark_used(self, service_account_id: int) -> None:
        self.service_accounts[service_account_id].last_used_at = self._now()


class SQLAlchemyServiceAccountRegistry:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now or (lambda: datetime.now(UTC))

    def create(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        name: str,
        permissions: set[str],
        created_by: str,
    ) -> ServiceAccountRecord:
        now = self._now()
        with self._session_factory() as session:
            tenant = session.get(Tenant, tenant_id)
            if tenant is None:
                raise KeyError(tenant_id)
            project = None
            if project_id is not None:
                project = session.get(Project, project_id)
                if project is None:
                    raise KeyError(project_id)
            model = ServiceAccount(
                tenant_id=tenant.id,
                project_id=project.id if project is not None else None,
                name=name,
                description=None,
                permissions_json=sorted(permissions),
                status="active",
                created_by=created_by,
                updated_by=created_by,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.flush()
            session.commit()
            return _record_from_model(model)

    def get(self, service_account_id: int) -> ServiceAccountRecord:
        with self._session_factory() as session:
            model = session.get(ServiceAccount, service_account_id)
            if model is None or model.is_deleted:
                raise KeyError(service_account_id)
            return _record_from_model(model)

    def list(self) -> list[ServiceAccountRecord]:
        with self._session_factory() as session:
            statement = (
                select(ServiceAccount)
                .where(ServiceAccount.is_deleted.is_(False))
                .order_by(ServiceAccount.created_at.desc())
            )
            return [_record_from_model(model) for model in session.scalars(statement)]

    def set_status(self, service_account_id: int, status: str) -> ServiceAccountRecord:
        with self._session_factory() as session:
            model = session.get(ServiceAccount, service_account_id)
            if model is None or model.is_deleted:
                raise KeyError(service_account_id)
            model.status = status
            model.updated_at = self._now()
            session.commit()
            return _record_from_model(model)

    def update(
        self,
        service_account_id: int,
        *,
        name: str | None = None,
        permissions: set[str] | None = None,
        status: str | None = None,
    ) -> ServiceAccountRecord:
        with self._session_factory() as session:
            model = session.get(ServiceAccount, service_account_id)
            if model is None or model.is_deleted:
                raise KeyError(service_account_id)
            if name is not None:
                model.name = name
            if permissions is not None:
                model.permissions_json = sorted(permissions)
            if status is not None:
                model.status = status
            model.updated_at = self._now()
            session.commit()
            return _record_from_model(model)

    def delete(self, service_account_id: int) -> ServiceAccountRecord:
        with self._session_factory() as session:
            model = session.get(ServiceAccount, service_account_id)
            if model is None or model.is_deleted:
                raise KeyError(service_account_id)
            model.status = "deleted"
            model.is_deleted = True
            model.deleted_at = self._now()
            model.updated_at = model.deleted_at
            session.commit()
            return _record_from_model(model)

    def mark_used(self, service_account_id: int) -> None:
        with self._session_factory() as session:
            model = session.get(ServiceAccount, service_account_id)
            if model is None:
                return
            model.last_used_at = self._now()
            model.updated_at = model.last_used_at
            session.commit()


def _record_from_model(model: ServiceAccount) -> ServiceAccountRecord:
    return ServiceAccountRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        name=model.name,
        permissions=set(model.permissions_json or []),
        created_by=model.created_by or "system",
        status=model.status,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )
