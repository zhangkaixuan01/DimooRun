from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class SemanticStoreProvider:
    id: str
    tenant_id: str
    project_id: str
    name: str
    embedding_model: str
    embedding_gateway_id: str | None
    connection_ref: str
    retention_policy_id: str | None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticStoreProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[str, SemanticStoreProvider] = {}

    def register(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        embedding_model: str,
        embedding_gateway_id: str | None,
        connection_ref: str,
        retention_policy_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticStoreProvider:
        provider = SemanticStoreProvider(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            embedding_model=embedding_model,
            embedding_gateway_id=embedding_gateway_id,
            connection_ref=connection_ref,
            retention_policy_id=retention_policy_id,
            metadata=metadata or {},
        )
        self.providers[provider.id] = provider
        return provider

    def get(self, provider_id: str) -> SemanticStoreProvider:
        return self.providers[provider_id]
