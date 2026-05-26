import ast
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from dimoo_run.packages.manifest import load_manifest


class ProjectSection(BaseModel):
    name: str
    tenant: str = "default"


class AgentSection(BaseModel):
    name: str
    path: str
    manifest: str


class AdapterToggle(BaseModel):
    enabled: bool = False


class AdaptersSection(BaseModel):
    langgraph: AdapterToggle = Field(default_factory=lambda: AdapterToggle(enabled=True))
    langchain_agent: AdapterToggle = Field(default_factory=AdapterToggle, alias="langchain-agent")
    deepagents: AdapterToggle = Field(default_factory=AdapterToggle)

    model_config = {"populate_by_name": True}


class DeploymentSection(BaseModel):
    agent: str
    version: str
    execution_profile: str


class ExecutionProfileSection(BaseModel):
    mode: Literal["in_process", "worker"]
    storage: str | None = None
    queue: str | None = None
    max_concurrency: int | None = None


class ModelGatewaySection(BaseModel):
    provider: str
    base_url: str | None = None
    secret: str

    @field_validator("secret")
    @classmethod
    def reject_inline_secret(cls, value: str) -> str:
        if value.startswith(("sk-", "pk-")):
            raise ValueError("model gateway secret must be an environment variable name")
        return value


class ObservabilitySection(BaseModel):
    tracing: str = "opentelemetry"
    langfuse: dict[str, bool] = Field(default_factory=lambda: {"enabled": False})


class StorageSection(BaseModel):
    metadata: str = "sqlite"
    queue: str = "in_process"
    object_store: str = "local"


class ProjectConfig(BaseModel):
    schema_version: str = "1.0"
    project: ProjectSection
    agents: list[AgentSection] = Field(default_factory=list)
    adapters: AdaptersSection = Field(default_factory=AdaptersSection)
    deployments: dict[str, DeploymentSection] = Field(default_factory=dict)
    execution_profiles: dict[str, ExecutionProfileSection] = Field(default_factory=dict)
    model_gateways: dict[str, ModelGatewaySection] = Field(default_factory=dict)
    policies: dict[str, object] = Field(default_factory=dict)
    observability: ObservabilitySection = Field(default_factory=ObservabilitySection)
    storage: StorageSection = Field(default_factory=StorageSection)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("unsupported dimoorun.yaml schema_version")
        return value

    @model_validator(mode="after")
    def validate_deployment_refs(self) -> "ProjectConfig":
        agent_names = {agent.name for agent in self.agents}
        profile_names = set(self.execution_profiles)
        for environment, deployment in self.deployments.items():
            if deployment.agent not in agent_names:
                raise ValueError(f"deployment {environment!r} references unknown agent")
            if deployment.execution_profile not in profile_names:
                raise ValueError(f"deployment {environment!r} references unknown execution_profile")
        return self


def load_project_config(path: str | Path) -> ProjectConfig:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return ProjectConfig.model_validate(payload)


def validate_project_workspace(path: str | Path) -> list[str]:
    workspace = Path(path)
    config = load_project_config(workspace / "dimoorun.yaml")
    errors: list[str] = []
    for agent in config.agents:
        agent_path = workspace / agent.path
        if not agent_path.exists():
            errors.append(f"{agent_path}: agent path was not found")
            continue
        manifest_path = workspace / agent.manifest
        try:
            manifest = load_manifest(manifest_path)
            errors.extend(_validate_entrypoint(agent_path, manifest.runtime.entrypoint))
        except Exception as exc:  # noqa: BLE001 - CLI validation must aggregate user errors.
            errors.append(f"{manifest_path}: {exc}")
    return errors


def _validate_entrypoint(agent_path: Path, entrypoint: str) -> list[str]:
    module_name, function_name = entrypoint.split(":", maxsplit=1)
    module_path = agent_path / Path(*module_name.split(".")).with_suffix(".py")
    if not module_path.exists():
        return [f"{module_path}: entrypoint module file was not found"]
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{module_path}: entrypoint module has invalid Python syntax: {exc.msg}"]
    function_names = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    if function_name not in function_names:
        return [f"{module_path}: entrypoint function {function_name!r} was not found"]
    return []


def write_default_workspace(path: str | Path, *, name: str) -> None:
    workspace = Path(path)
    agent_dir = workspace / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agent.py").write_text(
        "def create_agent():\n    return object()\n",
        encoding="utf-8",
    )
    (agent_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "name": name,
                "version": "0.1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create_agent",
                    "python": ">=3.11",
                },
                "capabilities": {"invoke": True, "stream": True},
                "dependencies": [],
                "required_secrets": ["NEWAPI_API_KEY"],
                "security": {"network_policy": "restricted", "allow_file_system_write": False},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (workspace / "dimoorun.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "project": {"name": name, "tenant": "default"},
                "agents": [
                    {
                        "name": name,
                        "path": f"./agents/{name}",
                        "manifest": f"./agents/{name}/manifest.yaml",
                    }
                ],
                "adapters": {
                    "langgraph": {"enabled": True},
                    "langchain-agent": {"enabled": False},
                    "deepagents": {"enabled": False},
                },
                "deployments": {
                    "dev": {
                        "agent": name,
                        "version": "0.1.0",
                        "execution_profile": "local-dev",
                    }
                },
                "execution_profiles": {"local-dev": {"mode": "in_process", "storage": "sqlite"}},
                "model_gateways": {"default": {"provider": "newapi", "secret": "NEWAPI_API_KEY"}},
                "policies": {"tool_approval": {"destructive": "required"}},
                "observability": {"tracing": "opentelemetry", "langfuse": {"enabled": False}},
                "storage": {"metadata": "sqlite", "queue": "in_process", "object_store": "local"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
