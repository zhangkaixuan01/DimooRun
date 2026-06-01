from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from dimoo_run.api.compat.auth import ProjectIdHeader, TenantIdHeader, require_compat_api_key
from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader, error_response
from dimoo_run.api.native.deployments import default_deployment_control
from dimoo_run.core.events import AgentEvent
from dimoo_run.deployments.service import (
    DeploymentNotFoundError,
    DeploymentRuntimeControlService,
    PolicyDeniedError,
)
from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.runtime.run_manager import InMemoryRunStore, RunManager, RuntimeRun
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend
from dimoo_run.security.api_keys import AuthenticatedActor
from dimoo_run.streaming.replay_buffer import ReplayBuffer
from dimoo_run.streaming.sse import encode_sse_event

router = APIRouter(prefix="/langgraph", tags=["compat-langgraph"])


class AssistantCreate(BaseModel):
    name: str
    deployment_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThreadCreate(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    assistant_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass
class CompatRuntime:
    run_store: InMemoryRunStore
    task_backend: InMemoryTaskBackend
    audit_log: InMemoryComplianceAuditLog
    replay_buffer: ReplayBuffer
    assistants: dict[str, dict[str, Any]]
    threads: dict[str, dict[str, Any]]
    runs: dict[int, dict[str, Any]]
    next_agent_id: int = 1
    next_agent_version_id: int = 1

    @classmethod
    def create(cls) -> "CompatRuntime":
        return cls(
            run_store=InMemoryRunStore(),
            task_backend=InMemoryTaskBackend(),
            audit_log=InMemoryComplianceAuditLog(),
            replay_buffer=ReplayBuffer(),
            assistants={},
            threads={},
            runs={},
        )

    @property
    def deployment_control(self) -> DeploymentRuntimeControlService:
        return default_deployment_control()

    @property
    def run_manager(self) -> RunManager:
        return RunManager(
            run_store=self.run_store,
            task_backend=self.task_backend,
            deployment_gate=self.deployment_control,
        )


_default_compat_runtime = CompatRuntime.create()


def default_compat_runtime() -> CompatRuntime:
    return _default_compat_runtime


def reset_compat_runtime() -> None:
    global _default_compat_runtime
    _default_compat_runtime = CompatRuntime.create()


def _guard(
    response: Response,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
) -> AuthenticatedActor | JSONResponse:
    return require_compat_api_key(response, authorization, tenant_id, project_id, request_id)


def _assistant_body(assistant_id: str, payload: AssistantCreate) -> dict[str, Any]:
    return {
        "assistant_id": assistant_id,
        "name": payload.name,
        "metadata": {
            **payload.metadata,
            "dimoorun_mapping": {
                "deployment_id": payload.deployment_id,
                "compat_api_version": "1.0",
            },
        },
    }


def _thread_not_found(thread_id: str, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=404,
        error_code="thread_not_found",
        message="Thread mapping was not found.",
        request_id=request_id,
        details={"thread_id": thread_id},
    )


def _assistant_not_found(assistant_id: str, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=404,
        error_code="assistant_not_found",
        message="Assistant mapping was not found.",
        request_id=request_id,
        details={"assistant_id": assistant_id},
    )


def _deployment_not_found(deployment_id: int, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=404,
        error_code="deployment_not_found",
        message="Deployment was not found.",
        request_id=request_id,
        details={"deployment_id": deployment_id},
    )


def _policy_denied(exc: PolicyDeniedError, request_id: str | None) -> JSONResponse:
    return error_response(
        status_code=403,
        error_code=exc.error_code,
        message=exc.reason,
        request_id=request_id,
        details={},
    )


def _deployment_exists(
    *,
    runtime: CompatRuntime,
    deployment_id: int,
) -> bool:
    return deployment_id in runtime.deployment_control.deployments.deployments


def _validate_existing_deployment_binding(
    *,
    runtime: CompatRuntime,
    deployment_id: int | None,
    tenant_id: int,
    project_id: int | None,
    request_id: str | None,
) -> JSONResponse | None:
    if deployment_id is None:
        return None
    if not _deployment_exists(runtime=runtime, deployment_id=deployment_id):
        return None
    try:
        deployment = runtime.deployment_control.deployments.get(deployment_id)
    except DeploymentNotFoundError:
        return _deployment_not_found(deployment_id, request_id)
    if deployment.tenant_id != tenant_id or deployment.project_id != project_id:
        return _deployment_not_found(deployment_id, request_id)
    return None


def _thread_in_scope(thread: dict[str, Any], actor: AuthenticatedActor) -> bool:
    mapping = thread["metadata"]["dimoorun_mapping"]
    return bool(
        mapping["tenant_id"] == actor.tenant_id and mapping["project_id"] == actor.project_id
    )


def _assistant_in_scope(assistant: dict[str, Any], actor: AuthenticatedActor) -> bool:
    mapping = assistant["metadata"]["dimoorun_mapping"]
    return bool(
        mapping["tenant_id"] == actor.tenant_id and mapping["project_id"] == actor.project_id
    )


def _lookup_thread(
    *,
    runtime: CompatRuntime,
    thread_id: str,
    actor: AuthenticatedActor,
    request_id: str | None,
) -> dict[str, Any] | JSONResponse:
    thread = runtime.threads.get(thread_id)
    if thread is None or not _thread_in_scope(thread, actor):
        return _thread_not_found(thread_id, request_id)
    return thread


def _lookup_assistant(
    *,
    runtime: CompatRuntime,
    assistant_id: str,
    actor: AuthenticatedActor,
    request_id: str | None,
) -> dict[str, Any] | JSONResponse:
    assistant = runtime.assistants.get(assistant_id)
    if assistant is None or not _assistant_in_scope(assistant, actor):
        return _assistant_not_found(assistant_id, request_id)
    return assistant


def _lookup_run(
    *,
    runtime: CompatRuntime,
    thread_id: str,
    run_id: int,
    request_id: str | None,
) -> dict[str, Any] | JSONResponse:
    run = runtime.runs.get(run_id)
    if run is None or run["thread_id"] != thread_id:
        return error_response(
            status_code=404,
            error_code="run_not_found",
            message="Run mapping was not found.",
            request_id=request_id,
            details={"thread_id": thread_id, "run_id": run_id},
        )
    return run


def _run_body(
    *,
    runtime_run: RuntimeRun,
    task_id: int,
    thread_id: str,
    assistant_id: str,
    payload: RunCreate,
    status: str,
) -> dict[str, Any]:
    return {
        "run_id": runtime_run.run_id,
        "thread_id": thread_id,
        "assistant_id": assistant_id,
        "status": status,
        "metadata": {
            **payload.metadata,
            "dimoorun_mapping": {
                "run_id": runtime_run.run_id,
                "task_id": task_id,
                "event_log_required": True,
                "audit_required": True,
            },
        },
    }


async def _create_run(
    *,
    runtime: CompatRuntime,
    actor: AuthenticatedActor,
    thread_id: str,
    payload: RunCreate,
    status: str = "queued",
) -> dict[str, Any]:
    assistant = runtime.assistants[payload.assistant_id]
    mapping = assistant["metadata"]["dimoorun_mapping"]
    deployment_id = mapping["deployment_id"]
    manager_deployment_id = (
        deployment_id if _deployment_exists(runtime=runtime, deployment_id=deployment_id) else None
    )
    if actor.project_id is None:
        raise RuntimeError("project_scope_required")
    try:
        runtime_run, task_id = await runtime.run_manager.create_run_task(
            tenant_id=actor.tenant_id,
            project_id=actor.project_id,
            agent_id=mapping["agent_id"],
            agent_version_id=mapping["agent_version_id"],
            deployment_id=manager_deployment_id,
            input_data=payload.input,
            override_config={
                "compat_api": "langgraph",
                "assistant_id": payload.assistant_id,
                "deployment_id": deployment_id,
            },
            thread_id=thread_id,
        )
    except PolicyDeniedError as exc:
        raise exc
    body = _run_body(
        runtime_run=runtime_run,
        task_id=task_id,
        thread_id=thread_id,
        assistant_id=payload.assistant_id,
        payload=payload,
        status=status,
    )
    runtime.runs[runtime_run.run_id] = body
    runtime.replay_buffer.append(
        runtime_run.run_id,
        None,
        AgentEvent(type="run.created", payload={"task_id": task_id, "thread_id": thread_id}),
    )
    runtime.replay_buffer.append(
        runtime_run.run_id,
        None,
        AgentEvent(type="task.queued", payload={"task_id": task_id}),
    )
    runtime.audit_log.record(
        tenant_id=actor.tenant_id,
        project_id=actor.project_id,
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        action="compat.langgraph.run.create",
        resource_type="run",
        resource_id=runtime_run.run_id,
        result="allow",
        metadata={"thread_id": thread_id, "assistant_id": payload.assistant_id},
    )
    return body


def _record_run_action(
    *,
    runtime: CompatRuntime,
    actor: AuthenticatedActor,
    action: str,
    run: dict[str, Any],
    result: str = "allow",
) -> None:
    runtime.audit_log.record(
        tenant_id=actor.tenant_id,
        project_id=actor.project_id,
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        action=action,
        resource_type="run",
        resource_id=run["run_id"],
        result=result,
        metadata={"thread_id": run["thread_id"], "assistant_id": run["assistant_id"]},
    )


def _event_stream(run: dict[str, Any]) -> Iterator[str]:
    for event in default_compat_runtime().replay_buffer.replay(run["run_id"]):
        yield encode_sse_event(event)


@router.post("/assistants", status_code=201, response_model=None)
def create_assistant(
    response: Response,
    payload: AssistantCreate,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    denied = _validate_existing_deployment_binding(
        runtime=runtime,
        deployment_id=payload.deployment_id,
        tenant_id=auth.tenant_id,
        project_id=auth.project_id,
        request_id=x_request_id,
    )
    if denied is not None:
        return denied
    if payload.deployment_id is not None and _deployment_exists(
        runtime=runtime,
        deployment_id=payload.deployment_id,
    ):
        deployment = runtime.deployment_control.deployments.get(payload.deployment_id)
        agent_id = deployment.agent_id
        agent_version_id = deployment.agent_version_id
    else:
        agent_id = runtime.next_agent_id
        runtime.next_agent_id += 1
        agent_version_id = runtime.next_agent_version_id
        runtime.next_agent_version_id += 1
    assistant_id = f"assistant_{uuid4().hex[:12]}"
    body = _assistant_body(assistant_id, payload)
    body["metadata"]["dimoorun_mapping"]["tenant_id"] = auth.tenant_id
    body["metadata"]["dimoorun_mapping"]["project_id"] = auth.project_id
    body["metadata"]["dimoorun_mapping"]["agent_id"] = agent_id
    body["metadata"]["dimoorun_mapping"]["agent_version_id"] = agent_version_id
    runtime.assistants[assistant_id] = body
    return body


@router.get("/assistants", response_model=None)
def list_assistants(
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    return {
        "assistants": [
            assistant
            for assistant in runtime.assistants.values()
            if assistant["metadata"]["dimoorun_mapping"]["tenant_id"] == auth.tenant_id
            and assistant["metadata"]["dimoorun_mapping"]["project_id"] == auth.project_id
        ]
    }


@router.get("/assistants/{assistant_id}", response_model=None)
def get_assistant(
    assistant_id: str,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    assistant = default_compat_runtime().assistants.get(assistant_id)
    if assistant is None or not _assistant_in_scope(assistant, auth):
        return _assistant_not_found(assistant_id, x_request_id)
    return assistant


@router.post("/threads", status_code=201, response_model=None)
def create_thread(
    response: Response,
    payload: ThreadCreate | None = None,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    thread_id = f"thread_{uuid4().hex[:12]}"
    body = {
        "thread_id": thread_id,
        "metadata": {
            **(payload.metadata if payload else {}),
            "dimoorun_mapping": {
                "checkpoint_thread_id": thread_id,
                "tenant_id": auth.tenant_id,
                "project_id": auth.project_id,
            },
        },
    }
    default_compat_runtime().threads[thread_id] = body
    return body


@router.get("/threads/{thread_id}", response_model=None)
def get_thread(
    thread_id: str,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    thread = default_compat_runtime().threads.get(thread_id)
    if thread is None or not _thread_in_scope(thread, auth):
        return _thread_not_found(thread_id, x_request_id)
    return thread


@router.post("/threads/{thread_id}/runs", status_code=201, response_model=None)
async def create_run(
    thread_id: str,
    response: Response,
    payload: RunCreate,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    thread = _lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    assistant = _lookup_assistant(
        runtime=runtime,
        assistant_id=payload.assistant_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(assistant, JSONResponse):
        return assistant
    try:
        return await _create_run(runtime=runtime, actor=auth, thread_id=thread_id, payload=payload)
    except PolicyDeniedError as exc:
        return _policy_denied(exc, x_request_id)


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=None)
def get_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    thread = _lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    return _lookup_run(runtime=runtime, thread_id=thread_id, run_id=run_id, request_id=x_request_id)


@router.post("/threads/{thread_id}/runs/{run_id}/cancel", response_model=None)
async def cancel_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    thread = _lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    result = _lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(result, JSONResponse):
        return result
    task_id = result["metadata"]["dimoorun_mapping"]["task_id"]
    runtime.run_store.cancel_run(run_id)
    await runtime.task_backend.cancel(task_id)
    result["status"] = "cancelled"
    runtime.replay_buffer.append(
        run_id,
        None,
        AgentEvent(type="run.cancelled", payload={"task_id": task_id}),
    )
    _record_run_action(
        runtime=runtime,
        actor=auth,
        action="compat.langgraph.run.cancel",
        run=result,
    )
    return result


@router.post("/threads/{thread_id}/runs/{run_id}/join", response_model=None)
def join_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    thread = _lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    result = _lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(result, JSONResponse):
        return result
    runtime.run_store.complete_run(run_id, output={"compat_status": "joined"})
    result["status"] = "succeeded"
    runtime.replay_buffer.append(
        run_id,
        None,
        AgentEvent(type="run.completed", payload={"compat_status": "joined"}),
    )
    _record_run_action(
        runtime=runtime,
        actor=auth,
        action="compat.langgraph.run.join",
        run=result,
    )
    return result


@router.post("/threads/{thread_id}/runs/stream", response_model=None)
async def stream_run(
    thread_id: str,
    response: Response,
    payload: RunCreate,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> StreamingResponse | JSONResponse:
    auth = _guard(response, authorization, x_tenant_id, x_project_id, x_request_id)
    if isinstance(auth, JSONResponse):
        return auth
    runtime = default_compat_runtime()
    thread = _lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    assistant = _lookup_assistant(
        runtime=runtime,
        assistant_id=payload.assistant_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(assistant, JSONResponse):
        return assistant
    try:
        run = await _create_run(
            runtime=runtime,
            actor=auth,
            thread_id=thread_id,
            payload=payload,
            status="running",
        )
    except PolicyDeniedError as exc:
        return _policy_denied(exc, x_request_id)
    runtime.run_store.mark_run_running(run["run_id"])
    runtime.replay_buffer.append(
        run["run_id"],
        None,
        AgentEvent(type="run.started", payload={"thread_id": thread_id}),
    )
    return StreamingResponse(_event_stream(run), media_type="text/event-stream")
