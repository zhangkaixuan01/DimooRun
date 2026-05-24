import pytest
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
