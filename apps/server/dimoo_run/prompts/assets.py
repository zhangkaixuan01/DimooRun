from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import PolicyEngine, PolicyRequest


class AssetVersionError(ValueError):
    pass


@dataclass(frozen=True)
class PromptAsset:
    id: str
    tenant_id: str
    project_id: str
    name: str
    version: str
    content_ref: str
    variables_schema: dict[str, Any]
    created_by: str
    visibility_level: str = "internal"
    metadata: dict[str, Any] = field(default_factory=dict)


class PromptAssetStore:
    def __init__(self, *, policy_engine: PolicyEngine) -> None:
        self.policy_engine = policy_engine
        self.prompts: dict[tuple[str, str, str, str], PromptAsset] = {}

    def create_prompt(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        version: str,
        content_ref: str,
        variables_schema: dict[str, Any],
        created_by: str,
    ) -> PromptAsset:
        if version == "latest":
            raise AssetVersionError("prompt assets must use explicit versions")
        decision = self.policy_engine.evaluate(
            PolicyRequest(
                tenant_id=tenant_id,
                project_id=project_id,
                actor_id=created_by,
                actor_type="user",
                resource_type="prompt",
                resource_id=name,
                action="create",
            )
        )
        if decision.decision == Decision.deny:
            raise PermissionError(decision.reason or "prompt_create_denied")
        prompt = PromptAsset(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            version=version,
            content_ref=content_ref,
            variables_schema=variables_schema,
            created_by=created_by,
        )
        self.prompts[(tenant_id, project_id, name, version)] = prompt
        return prompt

    def resolve_prompt(
        self,
        tenant_id: str,
        project_id: str,
        name: str,
        version: str,
    ) -> PromptAsset:
        if version == "latest":
            raise AssetVersionError("production must bind explicit prompt versions")
        return self.prompts[(tenant_id, project_id, name, version)]
