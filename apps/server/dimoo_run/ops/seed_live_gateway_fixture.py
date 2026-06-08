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
AGENT_VERSION = "1.0.0"
PACKAGE_URI = "file://support-agent-live-smoke"
FRAMEWORK = "langgraph"
ADAPTER = "langgraph"
ENTRYPOINT = "agent:create_agent"
ENVIRONMENT = "local"


def _validated_manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "runtime": {
            "framework": FRAMEWORK,
            "adapter": ADAPTER,
            "entrypoint": ENTRYPOINT,
        }
    }
    manifest["validation_token"] = validation_token(
        package_uri=PACKAGE_URI,
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
                description="Fixture for published-surface live smoke.",
            )

        version = runtime.get_version(agent.id, AGENT_VERSION)
        if version is None:
            version = runtime.create_version(
                agent=agent,
                version=AGENT_VERSION,
                package_uri=PACKAGE_URI,
                framework=FRAMEWORK,
                adapter=ADAPTER,
                entrypoint=ENTRYPOINT,
                capabilities={},
                manifest=_validated_manifest(),
            )

        deployment = next(
            (
                item
                for item in deployments.list(tenant_id=1, project_id=1)
                if item.agent_id == agent.id and item.environment == ENVIRONMENT
            ),
            None,
        )
        if deployment is None:
            deployment = deployments.add(
                DeploymentRecord(
                    id=0,
                    tenant_id=1,
                    project_id=1,
                    agent_id=agent.id,
                    agent_version_id=version.id,
                    environment=ENVIRONMENT,
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
                        "agent_version_id": version.id,
                        "deployment_id": deployment.id,
                        "environment": ENVIRONMENT,
                    },
                    handle,
                    indent=2,
                )

        print(
            f"Seeded live gateway fixture: agent_id={agent.id} "
            f"agent_version_id={version.id} deployment_id={deployment.id}"
        )
        session.commit()


if __name__ == "__main__":
    run()
