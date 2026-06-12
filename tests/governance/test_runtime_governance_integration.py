from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dimoo_run.adapters.base.utils import maybe_await
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentResult
from dimoo_run.domain.models import (
    Agent,
    AgentVersion,
    ApprovalRequest,
    AuditLog,
    Deployment,
    HumanTask,
    ModelGateway,
    ModelPolicy,
    ModelUsageSnapshot,
    Policy,
    Run,
    Secret,
    Task,
    Tool,
)
from dimoo_run.packages.loader import load_entrypoint_result
from dimoo_run.packages.validation import validation_token
from dimoo_run.persistence.database import Base
from dimoo_run.worker.durable import execute_durable_once
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


class GovernedPackageAdapter:
    framework = "governed"

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> Any:
        return load_entrypoint_result(
            package_uri,
            manifest["runtime"]["entrypoint"],
            runtime_config,
        )

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        result = await maybe_await(agent(input_data, context))
        payload = result if isinstance(result, dict) else {"output": result}
        return AgentResult(output=payload)


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def build_manifest(package_uri: str) -> dict[str, Any]:
    manifest = {
        "name": "governed-agent",
        "runtime": {
            "framework": "governed",
            "adapter": "governed",
            "entrypoint": "agent:build_agent",
        },
        "capabilities": {"invoke": True},
        "secrets": [{"name": "OPENAI_API_KEY", "ref": "vault://project/model-openai"}],
    }
    return {
        **manifest,
        "validation_token": validation_token(
            package_uri=package_uri,
            framework="governed",
            adapter="governed",
            entrypoint="agent:build_agent",
            manifest=manifest,
        ),
    }


def write_governed_package(tmp_path) -> str:  # type: ignore[no-untyped-def]
    package_dir = tmp_path / "governed-package"
    package_dir.mkdir()
    (package_dir / "agent.py").write_text(
        "from __future__ import annotations\n"
        "from typing import Any\n"
        "\n"
        "def build_agent(config: dict[str, Any]):\n"
        "    executed: list[dict[str, Any]] = []\n"
        "    governance = dict(config.get('governance') or {})\n"
        "    async def invoke(input_data: dict[str, Any], context):\n"
        "        scenario = input_data['scenario']\n"
        "        if scenario == 'secret':\n"
        "            secret_ref = governance['secrets'].get_secret(\n"
        "                tenant_id=context.tenant_id,\n"
        "                project_id=context.project_id,\n"
        "                secret_name='OPENAI_API_KEY',\n"
        "                context=context,\n"
        "            )\n"
        "            return {'secret_ref': secret_ref}\n"
        "        if scenario == 'model':\n"
        "            async def execute(request):\n"
        "                return {\n"
        "                    'gateway_request_id': 'gw_req_1',\n"
        "                    'model': request.model,\n"
        "                    'usage': {\n"
        "                        'prompt_tokens': 12,\n"
        "                        'completion_tokens': 8,\n"
        "                        'cost': 0.02,\n"
        "                        'currency': 'USD',\n"
        "                    },\n"
        "                    'output': {'ok': True, 'model': request.model},\n"
        "                }\n"
        "            result = await governance['model_gateway'].run_chat(\n"
        "                context=context,\n"
        "                requested_model=input_data.get('model'),\n"
        "                estimated_cost=float(input_data.get('estimated_cost', 0.02)),\n"
        "                execute=execute,\n"
        "                timeout_seconds=0.1,\n"
        "            )\n"
        "            return {\n"
        "                'model': result.request.model,\n"
        "                'total_tokens': result.usage_snapshot.total_tokens,\n"
        "                'cost': result.usage_snapshot.cost,\n"
        "            }\n"
        "        if scenario == 'tool':\n"
        "            def handler(arguments: dict[str, Any]):\n"
        "                executed.append(arguments)\n"
        "                return {'updated': True, 'ticket_id': arguments['ticket_id']}\n"
        "            result = governance['tools'].call_by_name(\n"
        "                name='crm.update_ticket',\n"
        "                arguments={'ticket_id': 'T-100', 'status': 'closed'},\n"
        "                context=context,\n"
        "                actor_id='agent_runtime',\n"
        "                handler=handler,\n"
        "            )\n"
        "            return {\n"
        "                'status': result.status,\n"
        "                'human_task_id': result.human_task_id,\n"
        "                'executed_count': len(executed),\n"
        "            }\n"
        "        raise RuntimeError(f'unknown scenario: {scenario}')\n"
        "    return invoke\n",
        encoding="utf-8",
    )
    return str(package_dir)


def seed_runtime(
    session: Session,
    *,
    package_uri: str,
    deployment_config: dict[str, Any] | None = None,
) -> tuple[Run, Task]:
    agent = Agent(tenant_id=1, project_id=1, name="support", status="active")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        package_uri=package_uri,
        framework="governed",
        adapter="governed",
        entrypoint="agent:build_agent",
        manifest_json=build_manifest(package_uri),
        capabilities_json={},
        status="ready",
    )
    session.add(version)
    session.flush()
    deployment = Deployment(
        tenant_id=1,
        project_id=1,
        agent_id=agent.id,
        agent_version_id=version.id,
        environment="local",
        desired_status="active",
        runtime_status="running",
        replicas=1,
        config_json=dict(deployment_config or {}),
    )
    session.add(deployment)
    session.flush()
    run = Run(
        tenant_id=1,
        project_id=1,
        agent_id=agent.id,
        agent_version_id=version.id,
        deployment_id=deployment.id,
        input_ref='json:{"scenario":"unset"}',
    )
    session.add(run)
    session.flush()
    task = Task(run_id=run.id, tenant_id=1, project_id=1, queue="default")
    session.add(task)
    session.flush()
    return run, task


def set_run_input(run: Run, payload: dict[str, Any]) -> None:
    import json

    run.input_ref = "json:" + json.dumps(payload, sort_keys=True, separators=(",", ":"))


@pytest.mark.asyncio
async def test_runtime_secret_policy_blocks_real_worker_execution_and_audits_access(
    tmp_path: Path,
) -> None:
    session = make_session()
    package_uri = write_governed_package(tmp_path)
    run, task = seed_runtime(session, package_uri=package_uri)
    task.max_attempts = 1
    set_run_input(run, {"scenario": "secret"})
    session.add(
        Secret(
            tenant_id=1,
            project_id=1,
            name="OPENAI_API_KEY",
            provider="external",
            scope="project",
            status="active",
        )
    )
    session.add(
        Policy(
            tenant_id=1,
            project_id=1,
            type="admin",
            resource_type="secret",
            action="read",
            decision="deny",
            priority=10,
            condition_json={},
            reason="secret_access_denied",
            status="active",
            metadata_json={"name": "deny-secret-read"},
        )
    )
    session.commit()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        adapters={"governed": GovernedPackageAdapter()},  # type: ignore[dict-item]
    )

    assert result is not None
    assert result.status == "failed"
    session.refresh(run)
    session.refresh(task)
    secret = session.scalar(select(Secret).where(Secret.name == "OPENAI_API_KEY"))
    audits = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.resource_type == "secret")
            .order_by(AuditLog.id)
        )
    )
    assert run.status == "failed"
    assert run.error == "secret_access_denied"
    assert task.status == "dead_letter"
    assert secret is not None
    assert secret.last_used_at is None
    assert [record.result for record in audits] == ["deny"]
    assert audits[0].action == "secret.read"
    assert "vault://project/model-openai" not in str(audits[0].metadata_json)


@pytest.mark.asyncio
async def test_runtime_model_gateway_records_usage_and_runtime_audit(tmp_path) -> None:  # type: ignore[no-untyped-def]
    session = make_session()
    package_uri = write_governed_package(tmp_path)
    gateway = ModelGateway(
        tenant_id=1,
        project_id=1,
        name="primary-openai",
        provider_type="openai",
        base_url="https://api.openai.example/v1",
        credential_ref="secret:model-openai",
        default_model_group="support",
        status="active",
        metadata_json={},
    )
    session.add(gateway)
    session.flush()
    session.add(
        ModelPolicy(
            tenant_id=1,
            project_id=1,
            gateway_id=gateway.id,
            default_model="gpt-4.1-mini",
            allowed_models_json=["gpt-4.1-mini"],
            denied_models_json=[],
            max_tokens_per_run=256,
            max_cost_per_run=1.0,
            max_cost_per_day=5.0,
            fallback_policy_json={},
            on_budget_exceeded="reject",
            status="active",
        )
    )
    run, task = seed_runtime(
        session,
        package_uri=package_uri,
        deployment_config={"model_gateway_id": gateway.id},
    )
    set_run_input(run, {"scenario": "model"})
    session.commit()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        adapters={"governed": GovernedPackageAdapter()},  # type: ignore[dict-item]
    )

    assert result is not None
    assert result.status == "succeeded"
    session.refresh(run)
    session.refresh(task)
    snapshot = session.scalar(select(ModelUsageSnapshot).where(ModelUsageSnapshot.run_id == run.id))
    audits = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.resource_type == "model_gateway")
            .order_by(AuditLog.id)
        )
    )
    assert run.status == "succeeded"
    assert task.status == "succeeded"
    assert run.output_ref == 'json:{"cost":0.02,"model":"gpt-4.1-mini","total_tokens":20}'
    assert snapshot is not None
    assert snapshot.total_tokens == 20
    assert snapshot.cost == 0.02
    assert [record.result for record in audits] == ["allow"]
    assert audits[0].action == "model_gateway.use"


@pytest.mark.asyncio
async def test_runtime_tool_call_requires_approval_and_persists_human_task(tmp_path) -> None:  # type: ignore[no-untyped-def]
    session = make_session()
    package_uri = write_governed_package(tmp_path)
    tool = Tool(
        tenant_id=1,
        project_id=1,
        name="crm.update_ticket",
        description="Update a support ticket.",
        schema_json={"type": "object"},
        risk_level="write",
        status="active",
    )
    session.add(tool)
    session.flush()
    session.add(
        Policy(
            tenant_id=1,
            project_id=1,
            type="admin",
            resource_type="tool",
            action="call",
            decision="require_approval",
            priority=10,
            risk_level="write",
            condition_json={},
            reason="tool_approval_required",
            status="active",
            metadata_json={"name": "approve-ticket-write"},
        )
    )
    run, task = seed_runtime(
        session,
        package_uri=package_uri,
        deployment_config={"tool_ids": [tool.id]},
    )
    set_run_input(run, {"scenario": "tool"})
    session.commit()

    result = await execute_durable_once(
        session=session,
        worker_id="worker_1",
        adapters={"governed": GovernedPackageAdapter()},  # type: ignore[dict-item]
    )

    assert result is not None
    assert result.status == "succeeded"
    session.refresh(run)
    session.refresh(task)
    human_task = session.scalar(select(HumanTask).where(HumanTask.run_id == run.id))
    assert human_task is not None
    approval = session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.human_task_id == human_task.id)
    )
    audits = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.resource_type.in_(("tool", "human_task")))
            .order_by(AuditLog.id)
        )
    )
    assert run.status == "succeeded"
    assert task.status == "succeeded"
    assert approval is not None
    assert human_task.status == "pending"
    assert approval.status == "pending"
    assert approval.metadata_json["payload"]["tool_id"] == tool.id
    assert run.output_ref is not None
    assert run.output_ref.startswith('json:{"executed_count":0,"human_task_id":')
    assert '"status":"approval_required"}' in run.output_ref
    assert [(record.resource_type, record.result) for record in audits] == [
        ("tool", "require_approval"),
        ("human_task", "allow"),
        ("tool", "approval_required"),
    ]
