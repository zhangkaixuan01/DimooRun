import json

import pytest
from dimoo_run.adapters.langgraph.adapter import LangGraphAdapter
from dimoo_run.packages.manifest import AgentManifest, load_manifest
from pydantic import ValidationError


def test_manifest_validates_agent_package_contract(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """
name: support-agent
version: 0.1.0
schema_version: "1.0"
runtime:
  framework: langgraph
  adapter: langgraph
  entrypoint: agent:build_graph
  python: ">=3.11"
capabilities:
  invoke: true
  stream: true
  checkpoint: true
  resume: true
  interrupt: true
  tool_events: true
  token_usage: true
dependencies:
  - langgraph==1.2.1
  - langchain-core==1.4.0
required_secrets:
  - OPENAI_API_KEY
security:
  network_policy: restricted
  allow_file_system_write: false
""",
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert manifest.name == "support-agent"
    assert manifest.runtime.adapter == "langgraph"
    assert manifest.runtime.entrypoint == "agent:build_graph"
    assert manifest.capabilities.invoke is True
    assert manifest.security.allow_file_system_write is False


def test_support_agent_example_manifest_matches_langgraph_adapter_capabilities() -> None:
    manifest = load_manifest("examples/langgraph/support-agent/manifest.yaml")
    with open("examples/langgraph/support-agent/langgraph.json", encoding="utf-8") as f:
        langgraph_config = json.load(f)

    adapter_capabilities = LangGraphAdapter().capabilities.model_dump()
    manifest_capabilities = manifest.capabilities.model_dump()

    assert manifest.runtime.framework == "langgraph"
    assert manifest.runtime.adapter == "langgraph"
    assert manifest.runtime.entrypoint == "agent:build_graph"
    assert langgraph_config["dependencies"] == ["."]
    assert langgraph_config["graphs"] == {"support_agent": "./agent.py:build_graph"}
    assert manifest_capabilities == adapter_capabilities


def test_enterprise_support_agent_example_declares_real_llm_secret_and_tools() -> None:
    manifest = load_manifest("examples/langgraph/enterprise-support-agent/manifest.yaml")
    with open("examples/langgraph/enterprise-support-agent/langgraph.json", encoding="utf-8") as f:
        langgraph_config = json.load(f)

    assert manifest.name == "enterprise-support-agent"
    assert manifest.runtime.framework == "langgraph"
    assert manifest.runtime.adapter == "langgraph"
    assert manifest.runtime.entrypoint == "agent:build_graph"
    assert langgraph_config["dependencies"] == ["."]
    assert langgraph_config["graphs"] == {
        "enterprise_support_agent": "./agent.py:build_graph"
    }
    assert manifest.required_secrets == ["MODEL_GATEWAY_API_KEY"]
    assert manifest.capabilities.tool_events is True
    assert manifest.capabilities.model_events is True
    assert manifest.capabilities.token_usage is True


def test_manifest_rejects_unsupported_adapter() -> None:
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(
            {
                "name": "bad-agent",
                "version": "0.1.0",
                "schema_version": "1.0",
                "runtime": {
                    "framework": "crewai",
                    "adapter": "crewai",
                    "entrypoint": "agent:create",
                },
            }
        )


def test_manifest_rejects_invalid_entrypoint() -> None:
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(
            {
                "name": "bad-agent",
                "version": "0.1.0",
                "schema_version": "1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "missing_separator",
                },
            }
        )


def test_manifest_rejects_framework_adapter_mismatch() -> None:
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(
            {
                "name": "bad-agent",
                "version": "0.1.0",
                "schema_version": "1.0",
                "runtime": {
                    "framework": "crewai",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create",
                },
            }
        )


def test_manifest_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError):
        AgentManifest.model_validate(
            {
                "name": "future-agent",
                "version": "0.1.0",
                "schema_version": "2.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create",
                },
            }
        )


def test_manifest_rejects_inline_required_secret() -> None:
    with pytest.raises(ValidationError, match="required_secrets"):
        AgentManifest.model_validate(
            {
                "name": "bad-secret-agent",
                "version": "0.1.0",
                "schema_version": "1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:create",
                },
                "required_secrets": ["sk-live-plaintext"],
            }
        )
