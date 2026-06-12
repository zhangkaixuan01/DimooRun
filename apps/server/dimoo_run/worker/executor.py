import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dimoo_run.adapters.base.contract import AgentAdapter, CapabilityNotSupportedError
from dimoo_run.adapters.base.utils import maybe_await
from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentEvent, AgentResult
from dimoo_run.observability.otel import attach_trace_fields, trace_context_from_runtime
from dimoo_run.runtime.run_manager import RuntimeGovernanceBundle, RuntimeRunStore
from dimoo_run.scheduler.backend import RuntimeTaskBackend
from dimoo_run.scheduler.in_memory import StaleFencingTokenError
from dimoo_run.streaming.replay_buffer import ReplayBuffer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentRuntimeSpec:
    adapter: str
    package_uri: str
    manifest: dict[str, Any]
    runtime_config: dict[str, Any]
    secrets: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkerExecutionResult:
    task_id: int
    run_id: int
    attempt_id: int
    status: str


class WorkerExecutor:
    def __init__(
        self,
        *,
        worker_id: str,
        task_backend: RuntimeTaskBackend,
        run_store: RuntimeRunStore,
        replay_buffer: ReplayBuffer,
        adapters: dict[str, AgentAdapter],
        agent_specs: dict[int, AgentRuntimeSpec],
        runtime_spec_resolver: Callable[[Any], AgentRuntimeSpec] | None = None,
        governance_bundle_factory: Callable[
            [Any, RuntimeContext, dict[str, Any]],
            RuntimeGovernanceBundle | None,
        ]
        | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.task_backend = task_backend
        self.run_store = run_store
        self.replay_buffer = replay_buffer
        self.adapters = adapters
        self.agent_specs = agent_specs
        self.runtime_spec_resolver = runtime_spec_resolver
        self.governance_bundle_factory = governance_bundle_factory
        self._active_task_id: int | None = None
        self._active_worker_id: str | None = None
        self._active_fencing_token: int | None = None
        self._active_context: RuntimeContext | None = None

    async def execute_once(
        self,
        *,
        queue: str,
        lease_seconds: int = 30,
    ) -> WorkerExecutionResult | None:
        leased = await self.task_backend.lease(
            queue,
            worker_id=self.worker_id,
            lease_seconds=lease_seconds,
        )
        if leased is None:
            return None

        task_id = leased["task_id"]
        run_id = leased["run_id"]
        fencing_token = leased["fencing_token"]
        self.task_backend.mark_running(task_id, self.worker_id, fencing_token)
        self._active_task_id = task_id
        self._active_worker_id = self.worker_id
        self._active_fencing_token = fencing_token
        attempt = await self.run_store.create_attempt(
            run_id=run_id,
            task_id=task_id,
            worker_id=self.worker_id,
        )
        self._append(run_id, attempt.attempt_id, AgentEvent(type="attempt.started", payload={}))
        context: RuntimeContext | None = None

        try:
            run = self.run_store.get_run(run_id)
            spec = self._agent_spec_for_run(run)
            adapter = self._adapter(spec.adapter)
            runtime_config = {
                **spec.runtime_config,
                **leased.get("override_config", {}),
            }
            context = RuntimeContext(
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                run_id=run.run_id,
                task_id=task_id,
                agent_id=run.agent_id,
                agent_version_id=run.agent_version_id,
                deployment_id=run.deployment_id,
                thread_id=run.thread_id,
                environment=_runtime_environment(runtime_config),
                framework=getattr(adapter, "framework", spec.adapter),
                adapter=spec.adapter,
            )
            governance_bundle = self._governance_bundle(run, context, runtime_config)
            runtime_config = (
                governance_bundle.apply(runtime_config)
                if governance_bundle
                else runtime_config
            )
            trace = trace_context_from_runtime(context, worker_id=self.worker_id)
            context = RuntimeContext(
                tenant_id=context.tenant_id,
                project_id=context.project_id,
                run_id=context.run_id,
                task_id=context.task_id,
                agent_id=context.agent_id,
                agent_version_id=context.agent_version_id,
                deployment_id=context.deployment_id,
                user_id=context.user_id,
                service_account_id=context.service_account_id,
                thread_id=context.thread_id,
                session_id=context.session_id,
                request_id=trace.request_id,
                attempt_id=attempt.attempt_id,
                trace_id=trace.trace_id,
                correlation_id=trace.correlation_id,
                idempotency_key=context.idempotency_key,
                environment=_runtime_environment(runtime_config),
                framework=context.framework,
                adapter=context.adapter,
                agent_version=context.agent_version,
                deadline_at=context.deadline_at,
                permissions=list(context.permissions),
                secrets=dict(spec.secrets or {}),
                config=dict(runtime_config),
                metadata={
                    "worker_id": self.worker_id,
                    **dict(spec.metadata or {}),
                },
            )
            self._active_context = context
            logger.info(
                "worker.execute_once.started",
                extra=trace.as_log_fields(
                    run_id=run_id,
                    task_id=task_id,
                    attempt_id=attempt.attempt_id,
                ),
            )
            agent = await adapter.load(spec.package_uri, spec.manifest, runtime_config)
            timeout_seconds = runtime_config.get("timeout_seconds") or runtime_config.get("timeout")
            execution = self._execute_agent(adapter, agent, leased, context, attempt.attempt_id)
            if timeout_seconds is None:
                result = await execution
            else:
                result = await asyncio.wait_for(execution, timeout=float(timeout_seconds))
        except StaleFencingTokenError:
            self._clear_active_lease()
            raise
        except TimeoutError as exc:
            error = {
                "message": "run timed out",
                "type": exc.__class__.__name__,
                "error_code": "runtime_timeout",
            }
            self._assert_active_fencing()
            self.run_store.timeout_attempt(attempt.attempt_id, error)
            self._append(
                run_id,
                attempt.attempt_id,
                AgentEvent(type="attempt.timeout", payload=error),
            )
            will_retry = self.task_backend.will_retry(task_id)
            if not will_retry:
                self.run_store.timeout_run(run_id, error)
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="run.timeout", payload=error),
                )
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="stream.failed", payload=error),
                )
            else:
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="task.retrying", payload=error),
                )
            await self.task_backend.fail(task_id, self.worker_id, fencing_token, error)
            if context is not None:
                logger.warning(
                    "worker.execute_once.timeout",
                    extra=trace_context_from_runtime(
                        context,
                        worker_id=self.worker_id,
                    ).as_log_fields(
                        run_id=run_id,
                        task_id=task_id,
                        attempt_id=attempt.attempt_id,
                    ),
                )
            self._clear_active_lease()
            return WorkerExecutionResult(
                task_id=task_id,
                run_id=run_id,
                attempt_id=attempt.attempt_id,
                status="timeout",
            )
        except Exception as exc:
            error = {"message": str(exc), "type": exc.__class__.__name__}
            self._assert_active_fencing()
            self.run_store.fail_attempt(attempt.attempt_id, error)
            self._append(
                run_id,
                attempt.attempt_id,
                AgentEvent(type="attempt.failed", payload=error),
            )
            will_retry = self.task_backend.will_retry(task_id)
            if not will_retry:
                self.run_store.fail_run(run_id, error)
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="run.failed", payload=error),
                )
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="stream.failed", payload=error),
                )
            else:
                self._append(
                    run_id,
                    attempt.attempt_id,
                    AgentEvent(type="task.retrying", payload=error),
                )
            await self.task_backend.fail(task_id, self.worker_id, fencing_token, error)
            if context is not None:
                logger.exception(
                    "worker.execute_once.failed",
                    extra=trace_context_from_runtime(
                        context,
                        worker_id=self.worker_id,
                    ).as_log_fields(
                        run_id=run_id,
                        task_id=task_id,
                        attempt_id=attempt.attempt_id,
                    ),
                )
            self._clear_active_lease()
            return WorkerExecutionResult(
                task_id=task_id,
                run_id=run_id,
                attempt_id=attempt.attempt_id,
                status="failed",
            )

        self._assert_active_fencing()
        self.run_store.complete_run(run_id, result.output)
        self.run_store.complete_attempt(attempt.attempt_id)
        self._append(
            run_id,
            attempt.attempt_id,
            AgentEvent(type="run.completed", payload={"output": result.output}),
        )
        self._append(
            run_id,
            attempt.attempt_id,
            AgentEvent(type="stream.completed", payload={}),
        )
        await self.task_backend.complete(task_id, self.worker_id, fencing_token)
        if context is not None:
            logger.info(
                "worker.execute_once.completed",
                extra=trace_context_from_runtime(
                    context,
                    worker_id=self.worker_id,
                ).as_log_fields(
                    run_id=run_id,
                    task_id=task_id,
                    attempt_id=attempt.attempt_id,
                ),
            )
        self._clear_active_lease()
        return WorkerExecutionResult(
            task_id=task_id,
            run_id=run_id,
            attempt_id=attempt.attempt_id,
            status="succeeded",
        )

    def _append(self, run_id: int, attempt_id: int, event: AgentEvent) -> AgentEvent:
        self._assert_active_fencing()
        trace_context = self._active_context
        payload = event.payload
        if trace_context is not None:
            payload = attach_trace_fields(
                payload,
                trace_context_from_runtime(trace_context, worker_id=self.worker_id),
            )
        return self.replay_buffer.append(
            run_id,
            attempt_id,
            AgentEvent(
                type=event.type,
                payload=payload,
                run_id=event.run_id,
                attempt_id=event.attempt_id,
                sequence=event.sequence,
                event_id=event.event_id,
                framework=event.framework,
                visibility_level=event.visibility_level,
            ),
        )

    def _assert_active_fencing(self) -> None:
        if self._active_task_id is None or self._active_worker_id is None:
            return
        if self._active_fencing_token is None:
            return
        self.task_backend.assert_can_complete(
            self._active_task_id,
            self._active_worker_id,
            self._active_fencing_token,
        )

    def _clear_active_lease(self) -> None:
        self._active_task_id = None
        self._active_worker_id = None
        self._active_fencing_token = None
        self._active_context = None

    async def cancel_run(self, run_id: int, *, task_id: int | None = None) -> str:
        run = self.run_store.get_run(run_id)
        spec = self._agent_spec_for_run(run)
        adapter = self.adapters[spec.adapter]
        context = RuntimeContext(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            run_id=run.run_id,
            task_id=task_id,
            agent_id=run.agent_id,
            agent_version_id=run.agent_version_id,
            deployment_id=run.deployment_id,
            thread_id=run.thread_id,
            framework=getattr(adapter, "framework", spec.adapter),
            adapter=spec.adapter,
        )
        try:
            await adapter.cancel(run_id, context)
            status = "adapter_cancelled"
        except CapabilityNotSupportedError:
            status = "best_effort"
        trace = trace_context_from_runtime(context, worker_id=self.worker_id)
        self.replay_buffer.append(
            run_id,
            None,
            AgentEvent(
                type="run.cancel_requested",
                payload=attach_trace_fields({"status": status, "task_id": task_id}, trace),
            ),
        )
        logger.info(
            "worker.cancel_run.requested",
            extra=trace.as_log_fields(run_id=run_id, task_id=task_id, attempt_id=None),
        )
        return status

    def _agent_spec(self, agent_version_id: int) -> AgentRuntimeSpec:
        spec = self.agent_specs.get(agent_version_id)
        if spec is None:
            raise RuntimeError("worker_agent_version_not_found")
        return spec

    def _agent_spec_for_run(self, run: Any) -> AgentRuntimeSpec:
        if self.runtime_spec_resolver is not None:
            return self.runtime_spec_resolver(run)
        return self._agent_spec(run.agent_version_id)

    def _adapter(self, adapter_name: str) -> AgentAdapter:
        adapter = self.adapters.get(adapter_name)
        if adapter is None:
            raise RuntimeError("worker_adapter_not_found")
        return adapter

    def _governance_bundle(
        self,
        run: Any,
        context: RuntimeContext,
        runtime_config: dict[str, Any],
    ) -> RuntimeGovernanceBundle | None:
        if self.governance_bundle_factory is None:
            return None
        return self.governance_bundle_factory(run, context, runtime_config)

    async def _execute_agent(
        self,
        adapter: AgentAdapter,
        agent: Any,
        leased: dict[str, Any],
        context: RuntimeContext,
        attempt_id: int,
    ) -> AgentResult:
        if leased.get("execution_mode") != "stream":
            result = await adapter.invoke(agent, leased["input_data"], context)
            for event in result.events:
                self._append(context.run_id, attempt_id, event)
            return result

        stream_result: Any = adapter.stream(agent, leased["input_data"], context)
        stream = await maybe_await(stream_result)
        async for event in stream:
            self._append(context.run_id, attempt_id, event)
        return AgentResult(output={"streamed": True})


def _runtime_environment(runtime_config: dict[str, Any]) -> str | None:
    environment = runtime_config.get("environment")
    return str(environment) if isinstance(environment, str) and environment else None
