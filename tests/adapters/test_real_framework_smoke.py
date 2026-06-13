from __future__ import annotations

import tarfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from dimoo_run.adapters.deepagents.adapter import DeepAgentsAdapter
from dimoo_run.adapters.langchain_agent.adapter import LangChainAgentAdapter
from dimoo_run.core.context import RuntimeContext
from dimoo_run.packages.materializer import OciPackageMaterializer

ROOT = Path(__file__).resolve().parents[2]


def load_manifest(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def support_context(*, framework: str, adapter: str) -> RuntimeContext:
    return RuntimeContext(
        tenant_id=1,
        project_id=1,
        run_id=9001,
        task_id=41,
        agent_id=7,
        agent_version_id=11,
        deployment_id=5,
        thread_id="thread-smoke",
        framework=framework,
        adapter=adapter,
        secrets={"OPENAI_API_KEY": "secret:model-openai"},
        config={"configurable": {"channel": "support"}, "timeout_seconds": 30},
    )


async def collect_stream(stream: AsyncIterator[Any]) -> list[Any]:
    return [item async for item in stream]


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


@pytest.mark.asyncio
async def test_langchain_adapter_loads_real_example_and_supports_invoke_and_stream() -> None:
    adapter = LangChainAgentAdapter()
    package_dir = ROOT / "examples" / "langchain-agent" / "support-agent"
    manifest = load_manifest(package_dir / "manifest.yaml")
    agent = await adapter.load(
        str(package_dir),
        manifest,
        {"agent_message": "LangChain smoke response"},
    )

    result = await adapter.invoke(
        agent,
        {"messages": [{"role": "user", "content": "Need help with production rollout"}]},
        support_context(framework="langchain-agent", adapter="langchain-agent"),
    )
    events = await collect_stream(
        adapter.stream(
            agent,
            {"messages": [{"role": "user", "content": "Stream the rollout answer"}]},
            support_context(framework="langchain-agent", adapter="langchain-agent"),
        )
    )

    assert result.output["messages"][-1].content == "LangChain smoke response"
    assert events
    assert events[0].type == "agent.stream_chunk"
    assert events[0].framework == "langchain-agent"


@pytest.mark.asyncio
async def test_deepagents_adapter_loads_real_example_and_supports_invoke_and_stream() -> None:
    pytest.importorskip("deepagents")
    adapter = DeepAgentsAdapter()
    package_dir = ROOT / "examples" / "deepagents" / "support-agent"
    manifest = load_manifest(package_dir / "manifest.yaml")
    agent = await adapter.load(
        str(package_dir),
        manifest,
        {"response_prefix": "DeepAgents smoke"},
    )

    result = await adapter.invoke(
        agent,
        {"messages": [{"role": "user", "content": "Check the tenant policy"}]},
        support_context(framework="deepagents", adapter="deepagents"),
    )
    events = await collect_stream(
        adapter.stream(
            agent,
            {"messages": [{"role": "user", "content": "Stream the tenant answer"}]},
            support_context(framework="deepagents", adapter="deepagents"),
        )
    )

    assert result.output["messages"][-1].content == "DeepAgents smoke: Check the tenant policy"
    assert "files" in result.output
    assert events
    assert events[0].type == "agent.stream_chunk"
    assert events[0].framework == "deepagents"


@pytest.mark.asyncio
async def test_langchain_adapter_loads_materialized_oci_example_and_supports_invoke(
    tmp_path: Path,
) -> None:
    adapter = LangChainAgentAdapter()
    package_dir = ROOT / "examples" / "langchain-agent" / "support-agent"
    package_uri = "oci://registry.local/support-agent:1.0.0"
    oci_root, cache_root = write_oci_bundle(
        tmp_path,
        package_uri=package_uri,
        source_dir=package_dir,
    )
    materialized = OciPackageMaterializer(
        cache_root=cache_root,
        oci_roots=[oci_root],
    ).materialize(package_uri)
    manifest = load_manifest(package_dir / "manifest.yaml")
    agent = await adapter.load(
        materialized.load_path,
        manifest,
        {"agent_message": "LangChain OCI smoke response"},
    )

    result = await adapter.invoke(
        agent,
        {"messages": [{"role": "user", "content": "Need rollout guidance"}]},
        support_context(framework="langchain-agent", adapter="langchain-agent"),
    )

    assert result.output["messages"][-1].content == "LangChain OCI smoke response"


@pytest.mark.asyncio
async def test_deepagents_adapter_loads_materialized_oci_example_and_supports_invoke(
    tmp_path: Path,
) -> None:
    pytest.importorskip("deepagents")
    adapter = DeepAgentsAdapter()
    package_dir = ROOT / "examples" / "deepagents" / "support-agent"
    package_uri = "oci://registry.local/deepagents-support:1.0.0"
    oci_root, cache_root = write_oci_bundle(
        tmp_path,
        package_uri=package_uri,
        source_dir=package_dir,
    )
    materialized = OciPackageMaterializer(
        cache_root=cache_root,
        oci_roots=[oci_root],
    ).materialize(package_uri)
    manifest = load_manifest(package_dir / "manifest.yaml")
    agent = await adapter.load(
        materialized.load_path,
        manifest,
        {"response_prefix": "DeepAgents OCI smoke"},
    )

    result = await adapter.invoke(
        agent,
        {"messages": [{"role": "user", "content": "Check package materialization"}]},
        support_context(framework="deepagents", adapter="deepagents"),
    )

    assert result.output["messages"][-1].content == (
        "DeepAgents OCI smoke: Check the tenant policy"
    )
