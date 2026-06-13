from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    AgentVersion,
    ContainerPoolPolicy,
    Deployment,
    ExecutionProfile,
    ModelGateway,
    SandboxPolicy,
    Tool,
)
from dimoo_run.packages.materializer import (
    OciPackageMaterializer,
    PackageMaterializationError,
)
from dimoo_run.packages.validation import (
    manifest_has_valid_token,
    package_uri_allowed_in_runtime,
)
from dimoo_run.worker.executor import AgentRuntimeSpec


class PackageRegistryError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class ResolvedRuntimeBindings:
    config: dict[str, Any]
    secrets: dict[str, str]
    metadata: dict[str, Any]


class AgentRuntimeRegistry:
    def __init__(
        self,
        *,
        session: Session,
        runtime_mode: str | None = None,
        oci_materializer: OciPackageMaterializer | None = None,
    ) -> None:
        self.session = session
        settings = Settings.from_env()
        self.runtime_mode = runtime_mode or settings.runtime.mode
        self.oci_materializer = oci_materializer or OciPackageMaterializer.from_settings(settings)

    def resolve_for_run(
        self,
        *,
        agent_version_id: int,
        deployment_id: int | None,
        tenant_id: int,
        project_id: int | None,
    ) -> AgentRuntimeSpec:
        version = self.session.get(AgentVersion, agent_version_id)
        if version is None or version.is_deleted:
            raise PackageRegistryError("worker_agent_version_not_found")
        deployment = self._deployment(
            deployment_id=deployment_id,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        self._assert_ready_runtime(version)
        bindings = self._resolve_bindings(
            version=version,
            deployment=deployment,
            tenant_id=tenant_id,
            project_id=project_id,
        )
        resolved_package_uri, package_metadata = self._resolved_package_uri(version.package_uri)
        return AgentRuntimeSpec(
            adapter=version.adapter,
            package_uri=resolved_package_uri,
            manifest=version.manifest_json or {},
            runtime_config=bindings.config,
            secrets=bindings.secrets,
            metadata={**bindings.metadata, **package_metadata},
        )

    def _deployment(
        self,
        *,
        deployment_id: int | None,
        tenant_id: int,
        project_id: int | None,
    ) -> Deployment | None:
        if deployment_id is None:
            return None
        deployment = self.session.get(Deployment, deployment_id)
        if deployment is None or deployment.is_deleted:
            raise PackageRegistryError("deployment_not_found")
        if deployment.tenant_id != tenant_id or deployment.project_id != project_id:
            raise PackageRegistryError("deployment_scope_mismatch")
        return deployment

    def _assert_ready_runtime(self, version: AgentVersion) -> None:
        if version.status != "ready":
            raise PackageRegistryError("agent_version_not_ready")
        manifest = version.manifest_json or {}
        if not manifest_has_valid_token(
            package_uri=version.package_uri,
            framework=version.framework,
            adapter=version.adapter,
            entrypoint=version.entrypoint,
            manifest=manifest,
        ):
            raise PackageRegistryError("package_validation_required")
        if not package_uri_allowed_in_runtime(
            version.package_uri,
            runtime_mode=self.runtime_mode,
        ):
            raise PackageRegistryError("production_package_uri_not_allowed")

    def _resolve_bindings(
        self,
        *,
        version: AgentVersion,
        deployment: Deployment | None,
        tenant_id: int,
        project_id: int | None,
    ) -> ResolvedRuntimeBindings:
        manifest = version.manifest_json or {}
        deployment_config = dict(deployment.config_json) if deployment is not None else {}
        execution_profile = self._execution_profile(
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_config=deployment_config,
        )
        sandbox_policy = self._sandbox_policy(
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_config=deployment_config,
        )
        container_pool_policy = self._container_pool_policy(
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_config=deployment_config,
        )
        model_gateway = self._model_gateway(
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_config=deployment_config,
        )
        tools = self._tools(
            tenant_id=tenant_id,
            project_id=project_id,
            deployment_config=deployment_config,
        )
        secrets = _secret_bindings(manifest)
        timeout_seconds = (
            deployment_config.get("timeout_seconds")
            or (execution_profile.timeout_seconds if execution_profile is not None else None)
        )

        config: dict[str, Any] = {
            **manifest.get("runtime_config", {}),
            **deployment_config.get("runtime", {}),
            "environment": deployment.environment if deployment is not None else None,
            "deployment_config": deployment_config,
            "execution_profile": _execution_profile_payload(execution_profile),
            "model_gateway": _model_gateway_payload(model_gateway),
            "tool_gateway": {"tools": tools},
            "sandbox_policy": _sandbox_policy_payload(sandbox_policy),
            "container_pool_policy": _container_pool_payload(container_pool_policy),
            "secret_refs": secrets,
        }
        if timeout_seconds is not None:
            config["timeout_seconds"] = timeout_seconds

        metadata = {
            "execution_profile_id": (
                execution_profile.name if execution_profile is not None else None
            ),
            "model_gateway_id": model_gateway.id if model_gateway is not None else None,
            "sandbox_policy_id": sandbox_policy.id if sandbox_policy is not None else None,
            "container_pool_policy_id": (
                container_pool_policy.id if container_pool_policy is not None else None
            ),
            "tool_ids": [tool["id"] for tool in tools],
        }
        return ResolvedRuntimeBindings(
            config={key: value for key, value in config.items() if value is not None},
            secrets=secrets,
            metadata={key: value for key, value in metadata.items() if value is not None},
        )

    def _resolved_package_uri(self, package_uri: str) -> tuple[str, dict[str, Any]]:
        normalized = _normalize_package_uri(package_uri)
        if not package_uri.startswith("oci://"):
            return normalized, {"source_package_uri": package_uri}
        try:
            materialized = self.oci_materializer.materialize(package_uri)
        except PackageMaterializationError as exc:
            raise PackageRegistryError(exc.error_code) from exc
        return materialized.load_path, {
            "source_package_uri": materialized.source_uri,
            "materialized_package_path": materialized.load_path,
            "materialized_package_source": materialized.source_path,
        }

    def _execution_profile(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        deployment_config: dict[str, Any],
    ) -> ExecutionProfile | None:
        profile_name = deployment_config.get("execution_profile_id")
        if not isinstance(profile_name, str) or not profile_name:
            return None
        statement = select(ExecutionProfile).where(
            ExecutionProfile.tenant_id == tenant_id,
            ExecutionProfile.project_id == project_id,
            ExecutionProfile.name == profile_name,
            ExecutionProfile.status == "active",
            ExecutionProfile.is_deleted.is_(False),
        )
        profile = self.session.scalar(statement)
        if profile is None:
            raise PackageRegistryError("execution_profile_not_found")
        return profile

    def _model_gateway(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        deployment_config: dict[str, Any],
    ) -> ModelGateway | None:
        gateway_id = deployment_config.get("model_gateway_id")
        if not isinstance(gateway_id, int):
            return None
        gateway = self.session.get(ModelGateway, gateway_id)
        if gateway is None or gateway.is_deleted or gateway.status != "active":
            raise PackageRegistryError("model_gateway_not_found")
        if gateway.tenant_id != tenant_id or gateway.project_id != project_id:
            raise PackageRegistryError("model_gateway_scope_mismatch")
        return gateway

    def _sandbox_policy(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        deployment_config: dict[str, Any],
    ) -> SandboxPolicy | None:
        policy_id = deployment_config.get("sandbox_policy_id")
        if not isinstance(policy_id, int):
            return None
        policy = self.session.get(SandboxPolicy, policy_id)
        if policy is None or policy.is_deleted or policy.status != "active":
            raise PackageRegistryError("sandbox_policy_not_found")
        if policy.tenant_id != tenant_id or policy.project_id != project_id:
            raise PackageRegistryError("sandbox_policy_scope_mismatch")
        return policy

    def _container_pool_policy(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        deployment_config: dict[str, Any],
    ) -> ContainerPoolPolicy | None:
        policy_id = deployment_config.get("container_pool_policy_id")
        if not isinstance(policy_id, int):
            return None
        policy = self.session.get(ContainerPoolPolicy, policy_id)
        if policy is None or policy.is_deleted or policy.status != "active":
            raise PackageRegistryError("container_pool_policy_not_found")
        if policy.tenant_id != tenant_id or policy.project_id != project_id:
            raise PackageRegistryError("container_pool_policy_scope_mismatch")
        return policy

    def _tools(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        deployment_config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        tool_ids = deployment_config.get("tool_ids")
        if not isinstance(tool_ids, list):
            return []
        resolved: list[dict[str, Any]] = []
        for tool_id in tool_ids:
            if not isinstance(tool_id, int):
                raise PackageRegistryError("tool_binding_invalid")
            tool = self.session.get(Tool, tool_id)
            if tool is None or tool.is_deleted or tool.status != "active":
                raise PackageRegistryError("tool_not_found")
            if tool.tenant_id != tenant_id or tool.project_id != project_id:
                raise PackageRegistryError("tool_scope_mismatch")
            resolved.append(
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "risk_level": tool.risk_level,
                    "schema": tool.schema_json,
                }
            )
        return resolved


def _normalize_package_uri(package_uri: str) -> str:
    if package_uri.startswith("file://"):
        return package_uri.removeprefix("file://")
    if package_uri.startswith(("oci://", "memory://")):
        return package_uri
    if package_uri.startswith(("./", ".\\")):
        return str(Path(package_uri).resolve())
    return package_uri


def _secret_bindings(manifest: dict[str, Any]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    secrets = manifest.get("secrets", [])
    if isinstance(secrets, list):
        for item in secrets:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            ref = item.get("ref")
            if isinstance(name, str) and isinstance(ref, str):
                bindings[name] = ref
    required_secrets = manifest.get("required_secrets", [])
    if isinstance(required_secrets, list):
        for ref in required_secrets:
            if isinstance(ref, str) and ref not in bindings.values():
                bindings[ref] = ref
    return bindings


def _execution_profile_payload(profile: ExecutionProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "name": profile.name,
        "isolation_level": profile.isolation_level,
        "image": profile.image,
        "python_version": profile.python_version,
        "dependency_lock_required": profile.dependency_lock_required,
        "network_policy": profile.network_policy,
        "filesystem_policy": profile.filesystem_policy,
        "cpu_limit": profile.cpu_limit,
        "memory_limit": profile.memory_limit,
        "timeout_seconds": profile.timeout_seconds,
        "allowed_env": profile.allowed_env_json,
        "allowed_secret_refs": profile.allowed_secret_refs_json,
        "allowed_gateway_refs": profile.allowed_gateway_refs_json,
    }


def _model_gateway_payload(gateway: ModelGateway | None) -> dict[str, Any] | None:
    if gateway is None:
        return None
    return {
        "id": gateway.id,
        "name": gateway.name,
        "provider_type": gateway.provider_type,
        "base_url": gateway.base_url,
        "credential_ref": gateway.credential_ref,
        "default_model_group": gateway.default_model_group,
        "metadata": gateway.metadata_json,
    }


def _sandbox_policy_payload(policy: SandboxPolicy | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "id": policy.id,
        "name": policy.name,
        "isolation_level": policy.isolation_level,
        "network_policy": policy.network_policy,
        "filesystem_policy": policy.filesystem_policy,
        "metadata": policy.metadata_json,
    }


def _container_pool_payload(policy: ContainerPoolPolicy | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {
        "id": policy.id,
        "name": policy.name,
        "max_containers": policy.max_containers,
        "cpu_limit": policy.cpu_limit,
        "memory_limit": policy.memory_limit,
        "idle_timeout_seconds": policy.idle_timeout_seconds,
        "metadata": policy.metadata_json,
    }
