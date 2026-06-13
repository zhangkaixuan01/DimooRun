from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from dimoo_run.api.native.deployments import SQLAlchemyDeploymentStore
from dimoo_run.api.native.runtime import SQLAlchemyNativeRuntimeStore
from dimoo_run.core.config import Settings
from dimoo_run.deployments.service import DeploymentRecord
from dimoo_run.domain.enums import DeploymentDesiredStatus, DeploymentRuntimeStatus
from dimoo_run.domain.models import Run, RunAttempt, Task
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.persistence.repositories import AuditLogRepository, EventRepository

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
REPLAY_THREAD_ID = "trace-live-replay"


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

        replay_runtime = SQLAlchemyNativeRuntimeStore(session)
        replay_run, replay_task, _ = replay_runtime.create_task_run(
            tenant_id=1,
            project_id=1,
            agent=agent,
            agent_version=current_version,
            input_data={
                "ticket_id": "INC-LIVE-REPLAY",
                "message": "provider timeout",
            },
            thread_id=REPLAY_THREAD_ID,
            idempotency_key=None,
            endpoint=f"/v1/deployments/{gateway_deployment.id}/tasks",
            request_body={
                "input": {
                    "ticket_id": "INC-LIVE-REPLAY",
                    "message": "provider timeout",
                }
            },
            deployment_id=gateway_deployment.id,
        )
        started_at = datetime.now(UTC) - timedelta(milliseconds=4300)
        finished_at = datetime.now(UTC)
        run_model = session.get(Run, replay_run.id)
        task_model = session.get(Task, replay_task.id)
        if run_model is None or task_model is None:
            raise RuntimeError("Failed to load seeded replay run/task models.")
        run_model.status = "failed"
        run_model.framework = FRAMEWORK
        run_model.adapter = ADAPTER
        run_model.trace_id = REPLAY_THREAD_ID
        run_model.started_at = started_at
        run_model.finished_at = finished_at
        run_model.error = "provider timeout"
        task_model.status = "failed"
        task_model.attempt = 1
        task_model.worker_id = "worker_live_replay"
        task_model.started_at = started_at
        task_model.finished_at = finished_at
        task_model.error = "provider timeout"
        attempt = RunAttempt(
            run_id=run_model.id,
            task_id=task_model.id,
            attempt_no=1,
            worker_id="worker_live_replay",
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            error="provider timeout",
            latency_ms=4300,
        )
        session.add(attempt)
        session.flush()
        events = EventRepository(session)
        events.append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run_model.id,
            attempt_id=attempt.id,
            tenant_id=1,
            project_id=1,
            type="run.started",
            payload={
                "task_id": task_model.id,
                "worker_id": "worker_live_replay",
            },
        )
        events.append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run_model.id,
            attempt_id=attempt.id,
            tenant_id=1,
            project_id=1,
            type="attempt.failed",
            payload={
                "task_id": task_model.id,
                "worker_id": "worker_live_replay",
                "error": "provider timeout",
            },
        )
        events.append(
            event_id=f"event_{uuid4().hex[:12]}",
            run_id=run_model.id,
            attempt_id=attempt.id,
            tenant_id=1,
            project_id=1,
            type="run.failed",
            payload={
                "error": "provider timeout",
                "provider": "llm-a",
            },
        )
        AuditLogRepository(session).append(
            tenant_id=1,
            project_id=1,
            action="run.triage.seed",
            resource_type="run",
            resource_id=run_model.id,
            result="allow",
            actor_id="seed_live_gateway_fixture",
            request_id="req_live_replay_seed",
            metadata={
                "thread_id": REPLAY_THREAD_ID,
                "candidate_agent_version_id": candidate_version.id,
            },
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
                        "replay_triage": {
                            "agent_id": agent.id,
                            "source_agent_version_id": current_version.id,
                            "candidate_agent_version_id": candidate_version.id,
                            "deployment_id": gateway_deployment.id,
                            "source_run_id": run_model.id,
                            "source_task_id": task_model.id,
                            "thread_id": REPLAY_THREAD_ID,
                        },
                    },
                    handle,
                    indent=2,
                )

        print(
            f"Seeded live gateway fixture: agent_id={agent.id} "
            f"agent_version_id={current_version.id} deployment_id={gateway_deployment.id} "
            f"promotion_deployment_id={promotion_deployment.id} "
            f"candidate_agent_version_id={candidate_version.id} "
            f"replay_source_run_id={run_model.id}"
        )
        session.commit()


if __name__ == "__main__":
    run()
