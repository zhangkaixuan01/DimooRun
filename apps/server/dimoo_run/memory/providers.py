from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SemanticStoreProvider:
    id: int
    tenant_id: int
    project_id: int
    name: str
    embedding_model: str
    embedding_gateway_id: int | None
    connection_ref: str
    retention_policy_id: str | None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticStoreProviderRegistry:
    def __init__(self) -> None:
        self.providers: dict[int, SemanticStoreProvider] = {}
        self._next_provider_id = 0

    def register(
        self,
        *,
        tenant_id: int,
        project_id: int,
        name: str,
        embedding_model: str,
        embedding_gateway_id: int | None,
        connection_ref: str,
        retention_policy_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticStoreProvider:
        provider = SemanticStoreProvider(
            id=self._allocate_provider_id(),
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

    def get(self, provider_id: int) -> SemanticStoreProvider:
        return self.providers[provider_id]

    def _allocate_provider_id(self) -> int:
        self._next_provider_id += 1
        return self._next_provider_id
