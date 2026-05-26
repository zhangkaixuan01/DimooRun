from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from dimoo_run.adapters.base.capabilities import CapabilityModel

SupportedAdapter = Literal["langgraph", "langchain-agent", "deepagents"]


class RuntimeManifest(BaseModel):
    framework: str
    adapter: SupportedAdapter
    entrypoint: str
    python: str = ">=3.11"

    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("entrypoint must use 'module:function' format")
        module_name, function_name = value.split(":", maxsplit=1)
        if not module_name or not function_name:
            raise ValueError("entrypoint must use 'module:function' format")
        return value

    @model_validator(mode="after")
    def validate_framework_adapter_match(self) -> "RuntimeManifest":
        expected_framework = {
            "langgraph": "langgraph",
            "langchain-agent": "langchain-agent",
            "deepagents": "deepagents",
        }[self.adapter]
        if self.framework != expected_framework:
            raise ValueError(
                f"framework must be {expected_framework!r} when adapter is {self.adapter!r}"
            )
        return self


class SecurityManifest(BaseModel):
    network_policy: str = "restricted"
    allow_file_system_write: bool = False


class AgentManifest(BaseModel):
    name: str
    version: str
    schema_version: str = "1.0"
    runtime: RuntimeManifest
    capabilities: CapabilityModel = Field(default_factory=CapabilityModel)
    dependencies: list[str] = Field(default_factory=list)
    required_secrets: list[str] = Field(default_factory=list)
    security: SecurityManifest = Field(default_factory=SecurityManifest)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("unsupported manifest schema_version")
        return value

    @field_validator("required_secrets")
    @classmethod
    def validate_required_secrets_are_refs(cls, value: list[str]) -> list[str]:
        for secret_ref in value:
            if secret_ref.startswith(("sk-", "pk-")) or "=" in secret_ref:
                raise ValueError(
                    "required_secrets must contain secret reference names, not plaintext"
                )
        return value


def load_manifest(path: str | Path) -> AgentManifest:
    manifest_path = Path(path)
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return AgentManifest.model_validate(payload)
