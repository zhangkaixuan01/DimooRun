from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from dimoo_run.observability.policies import RedactionPolicy


@dataclass(frozen=True)
class ComplianceAuditRecord:
    id: int
    tenant_id: int
    project_id: int | None
    actor_id: str | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: int | None
    result: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryComplianceAuditLog:
    def __init__(self, *, redaction_policy: RedactionPolicy | None = None) -> None:
        self.redaction_policy = redaction_policy or RedactionPolicy(fields={"api_key", "secret"})
        self.records: list[ComplianceAuditRecord] = []
        self._next_id = 1

    def record(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        actor_id: str | None,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: int | None,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceAuditRecord:
        record = ComplianceAuditRecord(
            id=self._next_id,
            tenant_id=tenant_id,
            project_id=project_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            metadata=self.redaction_policy.apply(metadata or {}),
        )
        self._next_id += 1
        self.records.append(record)
        return record
