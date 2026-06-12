from collections.abc import Mapping
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.adapters.base.contract import AgentAdapter
from dimoo_run.core.events import AgentEvent
from dimoo_run.domain.models import AgentVersion, Policy
from dimoo_run.hitl.service import SQLAlchemyHumanTaskService
from dimoo_run.model_gateway.provider import SQLAlchemyModelGatewayProvider
from dimoo_run.packages.registry import AgentRuntimeRegistry
from dimoo_run.persistence.repositories import AuditLogRepository, EventRepository
from dimoo_run.policy.decisions import Decision
from dimoo_run.policy.engine import AuditRecord, PolicyEngine, StaticPolicyRule
from dimoo_run.runtime.run_manager import RuntimeGovernanceBundle
from dimoo_run.runtime.sqlalchemy_run_store import SQLAlchemyRunStore
from dimoo_run.scheduler.sqlalchemy_backend import SQLAlchemyTaskBackend
from dimoo_run.secrets.provider import SQLAlchemySecretProvider
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.tools.gateway import SQLAlchemyToolGateway
from dimoo_run.worker.executor import AgentRuntimeSpec, WorkerExecutionResult, WorkerExecutor


class SQLAlchemyReplayBuffer(ReplayBuffer):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.run_store = SQLAlchemyRunStore(session)

    def append(
        self,
        run_id: int,
        attempt_id: int | None,
        event: AgentEvent,
    ) -> AgentEvent:
        appended = super().append(run_id, attempt_id, event)
        run = self.run_store.get_run(run_id)
        EventRepository(self.session).append(
            event_id=appended.event_id or f"{run_id}:event",
            run_id=run_id,
            attempt_id=attempt_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            type=appended.type,
            payload=appended.payload,
            framework=appended.framework,
            visibility_level=appended.visibility_level,
        )
        self.session.flush()
        return appended


class RuntimeSpecRunRecord(Protocol):
    agent_version_id: int
    deployment_id: int | None
    tenant_id: int
    project_id: int | None


class DurableWorkerExecutorFactory:
    def __init__(
        self,
        *,
        session: Session,
        worker_id: str,
        adapters: Mapping[str, AgentAdapter],
    ) -> None:
        self.session = session
        self.worker_id = worker_id
        self.adapters = dict(adapters)
        self.registry = AgentRuntimeRegistry(session=session)

    def build(self) -> WorkerExecutor:
        versions = self.session.scalars(
            select(AgentVersion).where(AgentVersion.is_deleted.is_(False))
        )
        specs = {
            version.id: AgentRuntimeSpec(
                adapter=version.adapter,
                package_uri=version.package_uri,
                manifest=version.manifest_json or {},
                runtime_config={},
            )
            for version in versions
        }
        return WorkerExecutor(
            worker_id=self.worker_id,
            task_backend=SQLAlchemyTaskBackend(self.session),
            run_store=SQLAlchemyRunStore(self.session),
            replay_buffer=SQLAlchemyReplayBuffer(self.session),
            adapters=self.adapters,
            agent_specs=specs,
            runtime_spec_resolver=self._resolve_runtime_spec,
            governance_bundle_factory=self._resolve_runtime_governance,
        )

    def _resolve_runtime_spec(self, run: RuntimeSpecRunRecord) -> AgentRuntimeSpec:
        return self.registry.resolve_for_run(
            agent_version_id=run.agent_version_id,
            deployment_id=run.deployment_id,
            tenant_id=run.tenant_id,
            project_id=run.project_id,
        )

    def _resolve_runtime_governance(
        self,
        run: RuntimeSpecRunRecord,
        context: object,
        runtime_config: dict[str, object],
    ) -> RuntimeGovernanceBundle | None:
        _ = run, runtime_config
        if not hasattr(context, "tenant_id") or not hasattr(context, "project_id"):
            return None
        audit_sink = SQLAlchemyPolicyAuditSink(self.session)
        policy_engine = PolicyEngine(
            rules=_policy_rules(
                self.session,
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                environment=getattr(context, "environment", None),
            ),
            audit_sink=audit_sink,
        )
        return RuntimeGovernanceBundle(
            secret_provider=SQLAlchemySecretProvider(
                session=self.session,
                policy_engine=policy_engine,
            ),
            model_gateway=SQLAlchemyModelGatewayProvider(
                session=self.session,
                policy_engine=policy_engine,
            ),
            tool_gateway=SQLAlchemyToolGateway(
                session=self.session,
                policy_engine=policy_engine,
                human_tasks=SQLAlchemyHumanTaskService(
                    session=self.session,
                    audit_sink=audit_sink,
                ),
            ),
        )


async def execute_durable_once(
    *,
    session: Session,
    worker_id: str,
    queue: str = "default",
    adapters: Mapping[str, AgentAdapter],
    lease_seconds: int = 30,
) -> WorkerExecutionResult | None:
    executor = DurableWorkerExecutorFactory(
        session=session,
        worker_id=worker_id,
        adapters=adapters,
    ).build()
    return await executor.execute_once(queue=queue, lease_seconds=lease_seconds)


class SQLAlchemyPolicyAuditSink:
    def __init__(self, session: Session) -> None:
        self.session = session

    def write(self, record: AuditRecord) -> None:
        AuditLogRepository(self.session).append(
            tenant_id=record.tenant_id,
            project_id=record.project_id,
            actor_id=record.actor_id,
            actor_type=record.actor_type,
            action=f"{record.resource_type}.{record.action}",
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            result=record.result,
            metadata={
                "reason": record.reason,
                "matched_policy_ids": list(record.matched_policy_ids),
                **dict(record.metadata),
            },
        )
        self.session.flush()


def _policy_rules(
    session: Session,
    *,
    tenant_id: int,
    project_id: int | None,
    environment: str | None,
) -> list[StaticPolicyRule]:
    statement = (
        select(Policy)
        .where(
            Policy.tenant_id == tenant_id,
            Policy.project_id == project_id,
            Policy.status == "active",
            Policy.is_deleted.is_(False),
        )
        .order_by(Policy.priority.asc(), Policy.id.asc())
    )
    rules: list[StaticPolicyRule] = []
    for policy in session.scalars(statement):
        metadata = dict(policy.metadata_json or {})
        policy_environment = metadata.get("_environment")
        if environment is not None and policy_environment not in {None, environment}:
            continue
        decision = _decision_value(policy.decision)
        condition = dict(policy.condition_json or {})
        rules.append(
            StaticPolicyRule(
                policy_id=str(policy.id),
                tenant_id=policy.tenant_id,
                project_id=policy.project_id,
                environment=condition.get("environment")
                if isinstance(condition.get("environment"), str)
                else (str(policy_environment) if isinstance(policy_environment, str) else None),
                resource_type=policy.resource_type,
                resource_id=_int_or_none(condition.get("resource_id")),
                action=policy.action,
                risk_level=_string_or_none(condition.get("risk_level")) or policy.risk_level,
                decision=decision,
                reason=policy.reason or policy.decision,
                metadata=metadata,
            )
        )
    return rules


def _decision_value(value: str) -> Decision:
    try:
        return Decision(value)
    except ValueError:
        return Decision.allow


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None
