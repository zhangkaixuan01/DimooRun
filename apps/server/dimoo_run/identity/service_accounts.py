from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class ServiceAccountRecord:
    id: str
    tenant_id: str
    project_id: str | None
    name: str
    permissions: set[str]
    created_by: str
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None


class ServiceAccountRegistry:
    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self.service_accounts: dict[str, ServiceAccountRecord] = {}

    def create(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        permissions: set[str],
        created_by: str,
    ) -> ServiceAccountRecord:
        record = ServiceAccountRecord(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            permissions=set(permissions),
            created_by=created_by,
            created_at=self._now(),
        )
        self.service_accounts[record.id] = record
        return record

    def get(self, service_account_id: str) -> ServiceAccountRecord:
        return self.service_accounts[service_account_id]

    def mark_used(self, service_account_id: str) -> None:
        self.service_accounts[service_account_id].last_used_at = self._now()
