from __future__ import annotations

import json
import os

from dimoo_run.api.native.deployments import SQLAlchemyDeploymentStore
from dimoo_run.api.native.runtime import SQLAlchemyNativeRuntimeStore
from dimoo_run.core.config import Settings
from dimoo_run.deployments.service import DeploymentRecord
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import create_session_factory

AGENT_NAME = "live-browser-support-agent"
CURRENT_AGENT_VERSION = "1.0.0"
CANDIDATE_AGENT_VERSION = "1.1.0"
CURRENT_PACKAGE_URI = "file://support-agent-live-smoke"
CANDIDATE_PACKAGE_URI = "file://support-agent-live-smoke-candidate"
FRAMEWORK = "langgraph"
ADAPTER = "langgraph"
ENTRYPOINT = "agent:create_agent"
GATEWAY_ENVIRONMENT = "local"
PROMOTION_ENVIRONMENT = "production"


def _validated_manifest(*, package_uri: str) -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime": {
            "framework": FRAMEWORK,
            "adapter": ADAPTER,
            "entrypoint": ENTRYPOINT,
        }
    }
    manifest["validation_token"] = validation_token(
        package_uri=package_uri,
        framework=FRAMEWORK,
        adapter=ADAPTER,
        entrypoint=ENTRYPOINT,
        manifest=manifest,
    )
    return manifest


def run() -> None:
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database.url)
    with session_factory() as session:
        runtime = SQLAlchemyNativeRuntimeStore(session)
        deployments = SQLAlchemyDeploymentStore(session)

        agent = next(
            (
                item
                for item in runtime.list_agents(tenant_id=1, project_id=1)
                if item.name == AGENT_NAME
            ),
            None,
        )
        if agent is None:
            agent = runtime.create_agent(
                tenant_id=1,
                project_id=1,
                name=AGENT_NAME,
                description="Fixture for live browser workflow smoke tests.",
            )

        current_version = runtime.get_version(agent.id, CURRENT_AGENT_VERSION)
        if current_version is None:
            current_version = runtime.create_version(
                agent=agent,
                version=CURRENT_AGENT_VERSION,
                package_uri=CURRENT_PACKAGE_URI,
                framework=FRAMEWORK,
                adapter=ADAPTER,
                entrypoint=ENTRYPOINT,
                capabilities={},
                manifest=_validated_manifest(package_uri=CURRENT_PACKAGE_URI),
            )

        candidate_version = runtime.get_version(agent.id, CANDIDATE_AGENT_VERSION)
        if candidate_version is None:
            candidate_version = runtime.create_version(
                agent=agent,
                version=CANDIDATE_AGENT_VERSION,
                package_uri=CANDIDATE_PACKAGE_URI,
                framework=FRAMEWORK,
                adapter=ADAPTER,
                entrypoint=ENTRYPOINT,
                capabilities={},
                manifest=_validated_manifest(package_uri=CANDIDATE_PACKAGE_URI),
            )

        gateway_deployment = next(
            (
                item
                for item in deployments.list(tenant_id=1, project_id=1)
                if item.agent_id == agent.id and item.environment == GATEWAY_ENVIRONMENT
            ),
            None,
        )
        if gateway_deployment is None:
            gateway_deployment = deployments.add(
                DeploymentRecord(
                    id=0,
                    tenant_id=1,
                    project_id=1,
                    agent_id=agent.id,
                    agent_version_id=current_version.id,
                    environment=GATEWAY_ENVIRONMENT,
                    desired_status=DeploymentDesiredStatus.active,
                    runtime_status=DeploymentRuntimeStatus.not_loaded,
                    replicas=1,
                    config_json={},
                )
            )

        promotion_deployment = next(
            (
                item
                for item in deployments.list(tenant_id=1, project_id=1)
                if item.agent_id == agent.id and item.environment == PROMOTION_ENVIRONMENT
            ),
            None,
        )
        if promotion_deployment is None:
            promotion_deployment = deployments.add(
                DeploymentRecord(
                    id=0,
                    tenant_id=1,
                    project_id=1,
                    agent_id=agent.id,
                    agent_version_id=current_version.id,
                    environment=PROMOTION_ENVIRONMENT,
                    desired_status=DeploymentDesiredStatus.active,
                    runtime_status=DeploymentRuntimeStatus.not_loaded,
                    replicas=1,
                    config_json={},
                )
            )

        fixture_path = os.getenv("DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE")
        if fixture_path:
            with open(fixture_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "agent_id": agent.id,
                        "agent_version_id": current_version.id,
                        "deployment_id": gateway_deployment.id,
                        "environment": GATEWAY_ENVIRONMENT,
                        "deployment_promotion": {
                            "agent_id": agent.id,
                            "current_agent_version_id": current_version.id,
                            "candidate_agent_version_id": candidate_version.id,
                            "deployment_id": promotion_deployment.id,
                            "environment": PROMOTION_ENVIRONMENT,
                        },
                    },
                    handle,
                    indent=2,
                )

        print(
            f"Seeded live gateway fixture: agent_id={agent.id} "
            f"agent_version_id={current_version.id} deployment_id={gateway_deployment.id} "
            f"promotion_deployment_id={promotion_deployment.id} "
            f"candidate_agent_version_id={candidate_version.id}"
        )
        session.commit()


if __name__ == "__main__":
    run()
