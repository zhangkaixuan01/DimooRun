from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

import pytest
from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    ContainerPoolPolicy,
    Deployment,
    ExecutionProfile,
    ModelGateway,
    SandboxPolicy,
    Tool,
)
from dimoo_run.packages.materializer import OciPackageMaterializer
from dimoo_run.packages.registry import AgentRuntimeRegistry, PackageRegistryError
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def ready_manifest(
    *,
    package_uri: str,
    framework: str = "langchain-agent",
    adapter: str = "langchain-agent",
    entrypoint: str = "support_agent:build_agent",
) -> dict[str, Any]:
    manifest = {
        "name": "support-agent",
        "runtime": {
            "framework": framework,
            "adapter": adapter,
            "entrypoint": entrypoint,
        },
        "secrets": [{"name": "OPENAI_API_KEY", "ref": "secret:model-openai"}],
        "required_secrets": ["secret:model-openai"],
        "capabilities": {"invoke": True, "stream": True},
    }
    return {
        **manifest,
        "validation_token": validation_token(
            package_uri=package_uri,
            framework=framework,
            adapter=adapter,
            entrypoint=entrypoint,
            manifest=manifest,
        ),
    }


def write_oci_bundle(
    tmp_path: Path,
    *,
    package_uri: str,
    source_dir: Path,
) -> tuple[Path, Path]:
    oci_root = tmp_path / "oci-root"
    cache_root = tmp_path / "package-cache"
    reference = package_uri.removeprefix("oci://")
    name, tag = reference.rsplit(":", maxsplit=1)
    registry, repository = name.split("/", maxsplit=1)
    bundle_path = oci_root / registry / repository / f"{tag}.tar.gz"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle_path, "w:gz") as archive:
        archive.add(source_dir, arcname=source_dir.name)
    return oci_root, cache_root


def test_runtime_registry_rejects_unsafe_local_package_uris_in_production() -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support-agent", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        package_uri="./examples/langchain-agent/support-agent",
        framework="langchain-agent",
        adapter="langchain-agent",
        entrypoint="support_agent:build_agent",
        manifest_json=ready_manifest(package_uri="./examples/langchain-agent/support-agent"),
        capabilities_json={"invoke": True, "stream": True},
        status="ready",
    )
    session.add(version)
    session.flush()

    registry = AgentRuntimeRegistry(session=session, runtime_mode="production")

    with pytest.raises(PackageRegistryError, match="production_package_uri_not_allowed"):
        registry.resolve_for_run(
            agent_version_id=version.id,
            deployment_id=None,
            tenant_id=1,
            project_id=1,
        )


def test_runtime_registry_requires_validated_ready_agent_versions() -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support-agent", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        package_uri="oci://registry.local/support-agent:1.0.0",
        framework="langchain-agent",
        adapter="langchain-agent",
        entrypoint="support_agent:build_agent",
        manifest_json={
            "name": "support-agent",
            "runtime": {
                "framework": "langchain-agent",
                "adapter": "langchain-agent",
                "entrypoint": "support_agent:build_agent",
            },
            "capabilities": {"invoke": True},
        },
        capabilities_json={"invoke": True},
        status="ready",
    )
    session.add(version)
    session.flush()

    registry = AgentRuntimeRegistry(session=session, runtime_mode="production")

    with pytest.raises(PackageRegistryError, match="package_validation_required"):
        registry.resolve_for_run(
            agent_version_id=version.id,
            deployment_id=None,
            tenant_id=1,
            project_id=1,
        )


def test_runtime_registry_resolves_execution_profile_gateway_tool_and_sandbox_bindings(
    tmp_path: Path,
) -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support-agent", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        package_uri="oci://registry.local/support-agent:1.0.0",
        framework="langchain-agent",
        adapter="langchain-agent",
        entrypoint="support_agent:build_agent",
        manifest_json=ready_manifest(package_uri="oci://registry.local/support-agent:1.0.0"),
        capabilities_json={"invoke": True, "stream": True},
        status="ready",
    )
    session.add(version)
    session.flush()
    deployment = Deployment(
        tenant_id=1,
        project_id=1,
        agent_id=agent.id,
        agent_version_id=version.id,
        environment="production",
        desired_status="active",
        runtime_status="ready",
        replicas=1,
        config_json={
            "execution_profile_id": "prod-worker",
            "model_gateway_id": 1,
            "sandbox_policy_id": 1,
            "container_pool_policy_id": 1,
            "tool_ids": [1],
            "runtime": {"configurable": {"channel": "support"}},
        },
    )
    session.add(deployment)
    session.add(
        ExecutionProfile(
            tenant_id=1,
            project_id=1,
            name="prod-worker",
            isolation_level="L3",
            image="registry.local/dimoorun:worker",
            python_version="3.11",
            dependency_lock_required=True,
            network_policy="egress-controlled",
            filesystem_policy="read-only",
            cpu_limit="1000m",
            memory_limit="1Gi",
            timeout_seconds=45,
            allowed_env_json=["LANGCHAIN_TRACING_V2"],
            allowed_secret_refs_json=["secret:model-openai"],
            allowed_gateway_refs_json=["gateway:model-openai"],
            status="active",
        )
    )
    session.add(
        ModelGateway(
            id=1,
            tenant_id=1,
            project_id=1,
            name="openai-prod",
            provider_type="openai_compatible",
            base_url="https://gateway.example/v1",
            credential_ref="secret:model-openai",
            default_model_group="gpt-4.1",
            status="active",
            metadata_json={"region": "cn"},
        )
    )
    session.add(
        SandboxPolicy(
            id=1,
            tenant_id=1,
            project_id=1,
            name="locked-down",
            isolation_level="L3",
            network_policy="deny_all",
            filesystem_policy="read_only",
            status="active",
            metadata_json={"mode": "process"},
        )
    )
    session.add(
        ContainerPoolPolicy(
            id=1,
            tenant_id=1,
            project_id=1,
            name="steady-pool",
            max_containers=6,
            cpu_limit="1500m",
            memory_limit="2Gi",
            idle_timeout_seconds=120,
            status="active",
            metadata_json={"strategy": "warm"},
        )
    )
    session.add(
        Tool(
            id=1,
            tenant_id=1,
            project_id=1,
            name="ticket_lookup",
            description="Lookup support ticket details.",
            schema_json={"type": "object"},
            risk_level="read",
            status="active",
        )
    )
    session.flush()

    package_uri = "oci://registry.local/support-agent:1.0.0"
    source_dir = Path("examples/langchain-agent/support-agent").resolve()
    oci_root, cache_root = write_oci_bundle(
        tmp_path,
        package_uri=package_uri,
        source_dir=source_dir,
    )
    registry = AgentRuntimeRegistry(
        session=session,
        runtime_mode="production",
        oci_materializer=OciPackageMaterializer(
            cache_root=cache_root,
            oci_roots=[oci_root],
        ),
    )
    spec = registry.resolve_for_run(
        agent_version_id=version.id,
        deployment_id=deployment.id,
        tenant_id=1,
        project_id=1,
    )

    metadata = spec.metadata or {}
    assert spec.package_uri.endswith("support-agent")
    assert metadata["source_package_uri"] == "oci://registry.local/support-agent:1.0.0"
    assert Path(str(metadata["materialized_package_path"])).exists()
    assert spec.secrets == {"OPENAI_API_KEY": "secret:model-openai"}
    assert spec.runtime_config["timeout_seconds"] == 45
    assert spec.runtime_config["execution_profile"]["name"] == "prod-worker"
    assert spec.runtime_config["model_gateway"]["base_url"] == "https://gateway.example/v1"
    assert spec.runtime_config["sandbox_policy"]["name"] == "locked-down"
    assert spec.runtime_config["container_pool_policy"]["name"] == "steady-pool"
    assert spec.runtime_config["tool_gateway"]["tools"][0]["name"] == "ticket_lookup"
    assert spec.runtime_config["configurable"] == {"channel": "support"}
    assert metadata == {
        "execution_profile_id": "prod-worker",
        "model_gateway_id": 1,
        "sandbox_policy_id": 1,
        "container_pool_policy_id": 1,
        "tool_ids": [1],
        "source_package_uri": "oci://registry.local/support-agent:1.0.0",
        "materialized_package_path": metadata["materialized_package_path"],
        "materialized_package_source": metadata["materialized_package_source"],
    }


def test_runtime_registry_materializes_oci_package_archive(tmp_path: Path) -> None:
    session = make_session()
    agent = Agent(tenant_id=1, project_id=1, name="support-agent", status="active")
    session.add(agent)
    session.flush()
    package_uri = "oci://registry.local/support-agent:1.0.0"
    source_dir = Path("examples/langchain-agent/support-agent").resolve()
    oci_root, cache_root = write_oci_bundle(
        tmp_path,
        package_uri=package_uri,
        source_dir=source_dir,
    )
    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        package_uri=package_uri,
        framework="langchain-agent",
        adapter="langchain-agent",
        entrypoint="support_agent:build_agent",
        manifest_json=ready_manifest(
            package_uri=package_uri,
            framework="langchain-agent",
            adapter="langchain-agent",
            entrypoint="support_agent:build_agent",
        ),
        capabilities_json={"invoke": True, "stream": True},
        status="ready",
    )
    session.add(version)
    session.flush()

    registry = AgentRuntimeRegistry(
        session=session,
        runtime_mode="production",
        oci_materializer=OciPackageMaterializer(
            cache_root=cache_root,
            oci_roots=[oci_root],
        ),
    )
    spec = registry.resolve_for_run(
        agent_version_id=version.id,
        deployment_id=None,
        tenant_id=1,
        project_id=1,
    )

    load_path = Path(spec.package_uri)
    assert load_path.exists()
    assert (load_path / "manifest.yaml").exists()
    metadata = spec.metadata or {}
    assert metadata["source_package_uri"] == package_uri
    assert str(metadata["materialized_package_source"]).endswith("1.0.0.tar.gz")
