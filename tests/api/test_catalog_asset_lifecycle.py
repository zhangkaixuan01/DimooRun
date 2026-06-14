import os
import tempfile
from uuid import uuid4

from dimoo_run.api.dependencies import reset_api_key_authenticator
from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    CatalogItem,
    ConfigAsset,
    Deployment,
    ModelGateway,
    Policy,
    Project,
    PromptAsset,
    Template,
    Tenant,
)
from dimoo_run.persistence.database import Base, create_session_factory
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker


def setup_function() -> None:
    os.environ["DIMOORUN_RUNTIME_MODE"] = "dev"
    os.environ["DIMOORUN_DEV_API_KEY"] = "dev-local-key"
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/dimoorun-catalog-{uuid4().hex}.db"
    reset_api_key_authenticator()


def admin_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev-local-key",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
        "X-Environment": "production",
        "X-Request-Id": request_id,
    }


def _session_factory() -> sessionmaker[Session]:
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        Base.metadata.create_all(session.get_bind())
    return session_factory


def _seed_scope() -> None:
    session_factory = _session_factory()
    with session_factory() as session:
        tenant = Tenant(name="Tenant", slug="tenant", status="active")
        session.add(tenant)
        session.flush()
        project = Project(tenant_id=tenant.id, name="Project", slug="project", status="active")
        session.add(project)
        session.commit()


def _seed_prompt_versions() -> tuple[int, int]:
    session_factory = _session_factory()
    with session_factory() as session:
        prompt_v1 = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="support-prompt",
            version="1.0.0",
            content_ref="inline:first",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={},
        )
        prompt_v2 = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="support-prompt",
            version="1.1.0",
            content_ref="inline:second",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={},
        )
        session.add(prompt_v1)
        session.add(prompt_v2)
        session.commit()
        return prompt_v1.id, prompt_v2.id


def test_catalog_asset_lifecycle_paths_are_registered() -> None:
    client = TestClient(create_app())
    paths = client.get("/openapi.json").json()["paths"]

    assert "/v1/catalog/items/{item_id}" in paths
    assert "/v1/catalog/items/{item_id}/publish" in paths
    assert "/v1/assets/prompts/{asset_id}" in paths
    assert "/v1/assets/prompts/{asset_id}/rollback" in paths


def test_prompt_validation_rejects_latest_and_invalid_refs() -> None:
    _seed_scope()
    session_factory = _session_factory()
    with session_factory() as session:
        prompt = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="broken-prompt",
            version="latest",
            content_ref="inline:bad",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={
                "secret_refs": ["bad-secret-ref"],
                "model_gateway_refs": ["missing-gateway"],
                "policy_refs": ["missing-policy"],
                "dependencies": [
                    {"kind": "prompt", "name": "missing", "version": "latest"},
                ],
            },
        )
        session.add(prompt)
        session.commit()
        prompt_id = prompt.id

    client = TestClient(create_app())
    response = client.post(
        f"/v1/assets/prompts/{prompt_id}/validate",
        headers=admin_headers("req_prompt_validate"),
        json={"audit_reason": "validate prompt asset"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["status"] == "failed"
    codes = {issue["code"] for issue in body["validation"]["issues"]}
    assert "explicit_version_required" in codes
    assert "secret_ref_invalid" in codes
    assert "model_gateway_ref_invalid" in codes
    assert "policy_ref_invalid" in codes
    assert "dependency_version_invalid" in codes


def test_prompt_lifecycle_supports_approve_publish_detail_and_rollback() -> None:
    _seed_scope()
    prompt_v1_id, prompt_v2_id = _seed_prompt_versions()
    client = TestClient(create_app())

    for prompt_id in (prompt_v1_id, prompt_v2_id):
        validated = client.post(
            f"/v1/assets/prompts/{prompt_id}/validate",
            headers=admin_headers(f"req_validate_{prompt_id}"),
            json={"audit_reason": "validate prompt asset"},
        )
        assert validated.status_code == 200
        assert validated.json()["validation"]["status"] == "passed"

        approved = client.post(
            f"/v1/assets/prompts/{prompt_id}/approve",
            headers=admin_headers(f"req_approve_{prompt_id}"),
            json={"audit_reason": "approve prompt asset"},
        )
        assert approved.status_code == 200
        assert approved.json()["item"]["status"] == "approved"

        published = client.post(
            f"/v1/assets/prompts/{prompt_id}/publish",
            headers=admin_headers(f"req_publish_{prompt_id}"),
            json={"audit_reason": "publish prompt asset"},
        )
        assert published.status_code == 200
        assert published.json()["item"]["status"] == "published"

    detail = client.get(
        f"/v1/assets/prompts/{prompt_v2_id}",
        headers=admin_headers("req_detail_prompt"),
    )
    assert detail.status_code == 200
    detail_body = detail.json()
    assert len(detail_body["version_history"]) == 2
    assert detail_body["diff_to_previous"]["has_changes"] is True

    rollback = client.post(
        f"/v1/assets/prompts/{prompt_v2_id}/rollback",
        headers=admin_headers("req_rollback_prompt"),
        json={"audit_reason": "rollback prompt asset", "target_version": "1.0.0"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["item"]["version"] == "1.0.0"
    assert rollback.json()["item"]["status"] == "published"
    assert rollback.json()["rolled_back_from"]["status"] == "deprecated"


def test_deprecate_blocks_when_active_deployment_uses_asset() -> None:
    _seed_scope()
    session_factory = _session_factory()
    with session_factory() as session:
        agent = Agent(tenant_id=1, project_id=1, name="support-agent", status="active")
        session.add(agent)
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version="0.1.0",
            package_uri="memory://support",
            framework="langgraph",
            adapter="langgraph",
            capabilities_json={},
            entrypoint="agent:create",
            manifest_json={},
            status="ready",
        )
        session.add(version)
        prompt = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="live-prompt",
            version="1.0.0",
            content_ref="inline:live",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={
                "validation": {"status": "passed"},
                "lifecycle": {"status": "published"},
            },
        )
        session.add(prompt)
        session.flush()
        deployment = Deployment(
            tenant_id=1,
            project_id=1,
            agent_id=agent.id,
            agent_version_id=version.id,
            environment="production",
            desired_status="active",
            runtime_status="ready",
            config_json={
                "prompt_asset_refs": [
                    {"name": "live-prompt", "version": "1.0.0"},
                ]
            },
        )
        session.add(deployment)
        session.commit()
        prompt_id = prompt.id

    client = TestClient(create_app())
    response = client.post(
        f"/v1/assets/prompts/{prompt_id}/deprecate",
        headers=admin_headers("req_deprecate_prompt"),
        json={"audit_reason": "deprecate prompt asset"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "asset_in_use_by_active_deployment"


def test_catalog_item_validation_and_detail_include_dependencies_and_usage() -> None:
    _seed_scope()
    session_factory = _session_factory()
    with session_factory() as session:
        gateway = ModelGateway(
            tenant_id=1,
            project_id=1,
            name="default-gateway",
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            credential_ref="secret:gateway",
            metadata_json={},
        )
        policy = Policy(
            tenant_id=1,
            project_id=1,
            type="admin",
            resource_type="catalog",
            action="use",
            decision="allow",
            priority=100,
            risk_level="medium",
            condition_json={},
            reason="allow catalog",
            status="active",
            metadata_json={"name": "catalog-allow"},
        )
        prompt = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="catalog-prompt",
            version="1.0.0",
            content_ref="inline:prompt",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={},
        )
        catalog = CatalogItem(
            tenant_id=1,
            project_id=1,
            type="tool",
            name="runtime-tool",
            provider="local",
            version="1.0.0",
            schema_json={"type": "object"},
            capabilities_json={"supports": ["invoke"]},
            risk_level="high",
            required_secrets_json=["secret:gateway"],
            required_permissions_json=["deployment:read"],
            runtime_requirements_json={
                "model_gateway_refs": ["default-gateway"],
                "policy_refs": ["catalog-allow"],
                "dependencies": [
                    {"kind": "prompt", "name": "catalog-prompt", "version": "1.0.0"},
                ],
            },
            status="draft",
        )
        agent = Agent(tenant_id=1, project_id=1, name="catalog-agent", status="active")
        session.add_all([gateway, policy, prompt, catalog, agent])
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version="0.2.0",
            package_uri="memory://catalog-agent",
            framework="langgraph",
            adapter="langgraph",
            capabilities_json={},
            entrypoint="agent:create",
            manifest_json={
                "catalog_item_refs": [
                    {"type": "tool", "name": "runtime-tool", "version": "1.0.0"},
                ]
            },
            status="ready",
        )
        session.add(version)
        session.commit()
        catalog_id = catalog.id

    client = TestClient(create_app())
    validated = client.post(
        f"/v1/catalog/items/{catalog_id}/validate",
        headers=admin_headers("req_catalog_validate"),
        json={"audit_reason": "validate catalog item"},
    )
    assert validated.status_code == 200
    assert validated.json()["validation"]["status"] == "passed"

    detail = client.get(
        f"/v1/catalog/items/{catalog_id}",
        headers=admin_headers("req_catalog_detail"),
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["validation"]["status"] == "passed"
    assert body["dependencies"][0]["name"] == "catalog-prompt"
    assert any(entry["resource_kind"] == "agent_version" for entry in body["used_by"])
    assert "high_risk_component" in body["risk_flags"]


def test_catalog_item_workflow_covers_mcp_endpoints_semantic_stores_and_runtime_components(
) -> None:
    _seed_scope()
    session_factory = _session_factory()
    with session_factory() as session:
        gateway = ModelGateway(
            tenant_id=1,
            project_id=1,
            name="default-gateway",
            provider_type="openai",
            base_url="https://api.openai.com/v1",
            credential_ref="secret:gateway",
            metadata_json={},
        )
        policy = Policy(
            tenant_id=1,
            project_id=1,
            type="admin",
            resource_type="catalog",
            action="use",
            decision="allow",
            priority=100,
            risk_level="medium",
            condition_json={},
            reason="allow catalog",
            status="active",
            metadata_json={"name": "catalog-allow"},
        )
        prompt = PromptAsset(
            tenant_id=1,
            project_id=1,
            name="catalog-prompt",
            version="1.0.0",
            content_ref="inline:prompt",
            variables_schema_json={"type": "object"},
            visibility_level="internal",
            metadata_json={},
        )
        config = ConfigAsset(
            tenant_id=1,
            project_id=1,
            name="retrieval-config",
            version="1.0.0",
            content_ref="inline:cfg",
            schema_json={"type": "object"},
            environment="production",
            metadata_json={},
        )
        template = Template(
            tenant_id=1,
            project_id=1,
            type="runtime_component_template",
            name="sandbox-template",
            version="1.0.0",
            content_ref="inline:template",
            schema_json={"type": "object"},
            metadata_json={},
        )
        mcp_endpoint = CatalogItem(
            tenant_id=1,
            project_id=1,
            type="mcp_endpoint",
            name="crm-mcp",
            provider="remote",
            version="1.0.0",
            schema_json={"type": "object"},
            capabilities_json={"invoke": True},
            risk_level="medium",
            required_secrets_json=["secret:gateway"],
            required_permissions_json=["tool:invoke"],
            runtime_requirements_json={
                "model_gateway_refs": ["default-gateway"],
                "policy_refs": ["catalog-allow"],
                "dependencies": [
                    {"kind": "prompt", "name": "catalog-prompt", "version": "1.0.0"},
                ],
            },
            status="draft",
        )
        semantic_store = CatalogItem(
            tenant_id=1,
            project_id=1,
            type="semantic_store",
            name="shared-memory",
            provider="chroma",
            version="1.0.0",
            schema_json={"type": "object"},
            capabilities_json={"search": True},
            risk_level="medium",
            required_secrets_json=[],
            required_permissions_json=["memory:query"],
            runtime_requirements_json={
                "dependencies": [
                    {"kind": "config", "name": "retrieval-config", "version": "1.0.0"},
                ],
            },
            status="draft",
        )
        runtime_component = CatalogItem(
            tenant_id=1,
            project_id=1,
            type="runtime_component",
            name="governed-sandbox",
            provider="native",
            version="1.0.0",
            schema_json={"type": "object"},
            capabilities_json={"sandbox": True},
            risk_level="critical",
            required_secrets_json=[],
            required_permissions_json=["deployment:write"],
            runtime_requirements_json={
                "dependencies": [
                    {
                        "kind": "template",
                        "type": "runtime_component_template",
                        "name": "sandbox-template",
                        "version": "1.0.0",
                    },
                ],
            },
            status="draft",
        )
        agent = Agent(tenant_id=1, project_id=1, name="runtime-agent", status="active")
        session.add_all(
            [
                gateway,
                policy,
                prompt,
                config,
                template,
                mcp_endpoint,
                semantic_store,
                runtime_component,
                agent,
            ]
        )
        session.flush()
        version = AgentVersion(
            agent_id=agent.id,
            version="0.3.0",
            package_uri="memory://runtime-agent",
            framework="langgraph",
            adapter="langgraph",
            capabilities_json={},
            entrypoint="agent:create",
            manifest_json={
                "catalog_item_refs": [
                    {"type": "mcp_endpoint", "name": "crm-mcp", "version": "1.0.0"},
                    {"type": "runtime_component", "name": "governed-sandbox", "version": "1.0.0"},
                ]
            },
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
            config_json={
                "catalog_item_refs": [
                    {"type": "runtime_component", "name": "governed-sandbox", "version": "1.0.0"},
                ]
            },
        )
        session.add(deployment)
        session.commit()
        ids = {
            "mcp": mcp_endpoint.id,
            "semantic": semantic_store.id,
            "runtime": runtime_component.id,
        }

    client = TestClient(create_app())
    for key in ("mcp", "semantic", "runtime"):
        validated = client.post(
            f"/v1/catalog/items/{ids[key]}/validate",
            headers=admin_headers(f"req_catalog_validate_{key}"),
            json={"audit_reason": f"validate {key} catalog item"},
        )
        assert validated.status_code == 200
        assert validated.json()["validation"]["status"] == "passed"

    approved = client.post(
        f"/v1/catalog/items/{ids['mcp']}/approve",
        headers=admin_headers("req_catalog_approve_mcp"),
        json={"audit_reason": "approve mcp endpoint"},
    )
    assert approved.status_code == 200
    assert approved.json()["item"]["status"] == "approved"

    published = client.post(
        f"/v1/catalog/items/{ids['mcp']}/publish",
        headers=admin_headers("req_catalog_publish_mcp"),
        json={"audit_reason": "publish mcp endpoint"},
    )
    assert published.status_code == 200
    assert published.json()["item"]["status"] == "published"

    semantic_detail = client.get(
        f"/v1/catalog/items/{ids['semantic']}",
        headers=admin_headers("req_catalog_detail_semantic"),
    )
    assert semantic_detail.status_code == 200
    semantic_body = semantic_detail.json()
    assert semantic_body["item"]["type"] == "semantic_store"
    assert semantic_body["item"]["provider"] == "chroma"
    assert semantic_body["dependencies"][0]["name"] == "retrieval-config"

    mcp_detail = client.get(
        f"/v1/catalog/items/{ids['mcp']}",
        headers=admin_headers("req_catalog_detail_mcp"),
    )
    assert mcp_detail.status_code == 200
    mcp_body = mcp_detail.json()
    assert mcp_body["item"]["type"] == "mcp_endpoint"
    assert any(entry["resource_kind"] == "agent_version" for entry in mcp_body["used_by"])

    runtime_detail = client.get(
        f"/v1/catalog/items/{ids['runtime']}",
        headers=admin_headers("req_catalog_detail_runtime"),
    )
    assert runtime_detail.status_code == 200
    runtime_body = runtime_detail.json()
    assert runtime_body["item"]["type"] == "runtime_component"
    assert "high_risk_component" in runtime_body["risk_flags"]
    assert any(entry["resource_kind"] == "deployment" for entry in runtime_body["used_by"])

    deprecate = client.post(
        f"/v1/catalog/items/{ids['runtime']}/deprecate",
        headers=admin_headers("req_catalog_deprecate_runtime"),
        json={"audit_reason": "deprecate runtime component"},
    )
    assert deprecate.status_code == 409
    assert deprecate.json()["error_code"] == "asset_in_use_by_active_deployment"
