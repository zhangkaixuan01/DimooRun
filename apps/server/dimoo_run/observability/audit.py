from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from dimoo_run.observability.policies import RedactionPolicy


@dataclass(frozen=True)
class ComplianceAuditRecord:
    id: str
    tenant_id: str
    project_id: str | None
    actor_id: str | None
    actor_type: str
    action: str
    resource_type: str
    resource_id: str | None
    result: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class InMemoryComplianceAuditLog:
    def __init__(self, *, redaction_policy: RedactionPolicy | None = None) -> None:
        self.redaction_policy = redaction_policy or RedactionPolicy(fields={"api_key", "secret"})
        self.records: list[ComplianceAuditRecord] = []

    def record(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        actor_id: str | None,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> ComplianceAuditRecord:
        record = ComplianceAuditRecord(
            id=str(uuid4()),
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
        self.records.append(record)
        return record
