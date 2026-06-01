from dataclasses import dataclass, field
from typing import Any

from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import PolicyEngine, PolicyRequest


@dataclass(frozen=True)
class CatalogItem:
    id: int
    tenant_id: int
    project_id: int | None
    type: str
    name: str
    provider: str
    version: str
    schema: dict[str, Any]
    risk_level: str
    required_permissions: set[str] = field(default_factory=set)
    capabilities: dict[str, Any] = field(default_factory=dict)
    required_secrets: set[str] = field(default_factory=set)
    runtime_requirements: dict[str, Any] = field(default_factory=dict)
    status: str = "active"


class CatalogService:
    def __init__(self, *, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine
        self.items: dict[int, CatalogItem] = {}

    def register(self, item: CatalogItem, *, actor_id: str | None) -> CatalogItem:
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=item.tenant_id,
                project_id=item.project_id,
                actor_id=actor_id,
                actor_type="user" if actor_id else "system",
                resource_type="catalog",
                resource_id=item.id,
                action="create",
                risk_level=item.risk_level,
            )
        )
        if decision.decision == Decision.deny:
            raise PermissionError(decision.reason or "catalog_create_denied")
        self.items[item.id] = item
        return item
