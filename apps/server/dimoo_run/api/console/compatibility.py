from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dimoo_run.api.compat import langgraph as compat_langgraph
from dimoo_run.api.compat.auth import (
    ProjectIdHeader,
    TenantIdHeader,
    require_compat_api_key,
)
from dimoo_run.api.dependencies import AuthorizationHeader, RequestIdHeader, error_response
from dimoo_run.compatibility import build_migration_report, default_golden_runner
from dimoo_run.core.events import AgentEvent
from dimoo_run.deployments.service import PolicyDeniedError
from dimoo_run.security.api_keys import AuthenticatedActor
from dimoo_run.streaming.replay_buffer import ReplayExpiredError

router = APIRouter(prefix="/v1/console/compatibility", tags=["console-compatibility"])


class CompatibilityMigrationPayload(BaseModel):
    framework: str = "langgraph"
    adapter: str = "langgraph"
    capabilities: list[str] = Field(default_factory=list)
    streaming_modes: list[str] = Field(default_factory=list)
    required_secrets: list[str] = Field(default_factory=list)
    custom_tools: list[str] = Field(default_factory=list)
    uses_checkpointing: bool = False
    requires_interrupts: bool = False


class CompatibilityAssistantPayload(BaseModel):
    name: str
    deployment_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompatibilityThreadPayload(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompatibilityRunPayload(BaseModel):
    assistant_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _compat_actor(
    *,
    response: Response,
    authorization: str | None,
    tenant_id: int | None,
    project_id: int | None,
    request_id: str | None,
    required_scope: str,
) -> AuthenticatedActor | JSONResponse:
    return require_compat_api_key(
        response,
        authorization,
        tenant_id,
        project_id,
        request_id,
        required_scope=required_scope,
    )


@router.get("/langgraph/assistants", response_model=None)
def list_langgraph_assistants(
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    items = [
        _wrap_result(
            operation="assistant.list",
            compat_response=assistant,
            native_resources=_assistant_resources(assistant),
        )
        for assistant in runtime.assistants.values()
        if compat_langgraph._assistant_in_scope(assistant, auth)
    ]
    return {"items": items, "count": len(items), "request_id": x_request_id}


@router.post("/langgraph/assistants", response_model=None)
def create_langgraph_assistant(
    response: Response,
    payload: CompatibilityAssistantPayload,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    denied = compat_langgraph._validate_existing_deployment_binding(
        runtime=runtime,
        deployment_id=payload.deployment_id,
        tenant_id=auth.tenant_id,
        project_id=auth.project_id,
        request_id=x_request_id,
    )
    if denied is not None:
        return denied
    if payload.deployment_id is not None and compat_langgraph._deployment_exists(
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
    assistant = compat_langgraph._assistant_body(
        assistant_id,
        compat_langgraph.AssistantCreate.model_validate(payload.model_dump()),
    )
    assistant["metadata"]["dimoorun_mapping"]["tenant_id"] = auth.tenant_id
    assistant["metadata"]["dimoorun_mapping"]["project_id"] = auth.project_id
    assistant["metadata"]["dimoorun_mapping"]["agent_id"] = agent_id
    assistant["metadata"]["dimoorun_mapping"]["agent_version_id"] = agent_version_id
    runtime.assistants[assistant_id] = assistant
    return _wrap_result(
        operation="assistant.create",
        compat_response=assistant,
        native_resources=_assistant_resources(assistant),
    )


@router.get("/langgraph/assistants/{assistant_id}", response_model=None)
def get_langgraph_assistant(
    assistant_id: str,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    assistant = compat_langgraph._lookup_assistant(
        runtime=compat_langgraph.default_compat_runtime(),
        assistant_id=assistant_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(assistant, JSONResponse):
        return assistant
    return _wrap_result(
        operation="assistant.get",
        compat_response=assistant,
        native_resources=_assistant_resources(assistant),
    )


@router.post("/langgraph/threads", response_model=None)
def create_langgraph_thread(
    response: Response,
    payload: CompatibilityThreadPayload | None = None,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    thread_id = f"thread_{uuid4().hex[:12]}"
    thread = {
        "thread_id": thread_id,
        "metadata": {
            **((payload.metadata if payload else {}) or {}),
            "dimoorun_mapping": {
                "checkpoint_thread_id": thread_id,
                "tenant_id": auth.tenant_id,
                "project_id": auth.project_id,
            },
        },
    }
    compat_langgraph.default_compat_runtime().threads[thread_id] = thread
    return _wrap_result(
        operation="thread.create",
        compat_response=thread,
        native_resources=_thread_resources(thread),
    )


@router.get("/langgraph/threads/{thread_id}", response_model=None)
def get_langgraph_thread(
    thread_id: str,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    thread = compat_langgraph._lookup_thread(
        runtime=compat_langgraph.default_compat_runtime(),
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    return _wrap_result(
        operation="thread.get",
        compat_response=thread,
        native_resources=_thread_resources(thread),
    )


@router.post("/langgraph/threads/{thread_id}/runs", response_model=None)
async def create_langgraph_run(
    thread_id: str,
    response: Response,
    payload: CompatibilityRunPayload,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    assistant = compat_langgraph._lookup_assistant(
        runtime=runtime,
        assistant_id=payload.assistant_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(assistant, JSONResponse):
        return assistant
    try:
        run = await compat_langgraph._create_run(
            runtime=runtime,
            actor=auth,
            thread_id=thread_id,
            payload=compat_langgraph.RunCreate.model_validate(payload.model_dump()),
        )
    except PolicyDeniedError as exc:
        return compat_langgraph._policy_denied(exc, x_request_id)
    return _wrap_result(
        operation="run.create",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
    )


@router.get("/langgraph/threads/{thread_id}/runs/{run_id}", response_model=None)
def get_langgraph_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    run = compat_langgraph._lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    assistant = runtime.assistants.get(run["assistant_id"])
    return _wrap_result(
        operation="run.status",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
    )


@router.get("/langgraph/threads/{thread_id}/runs/{run_id}/stream-status", response_model=None)
def get_langgraph_stream_status(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    run = compat_langgraph._lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    assistant = runtime.assistants.get(run["assistant_id"])
    events = runtime.replay_buffer.replay(run_id)
    stream_status = {
        "event_count": len(events),
        "latest_event_id": events[-1].event_id if events else None,
        "replay_from_event_id": events[0].event_id if events else None,
        "run_status": run["status"],
    }
    return _wrap_result(
        operation="run.stream_status",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
        stream_status=stream_status,
    )


@router.post("/langgraph/threads/{thread_id}/runs/stream-probe", response_model=None)
async def stream_probe_langgraph_run(
    thread_id: str,
    response: Response,
    payload: CompatibilityRunPayload,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    assistant = compat_langgraph._lookup_assistant(
        runtime=runtime,
        assistant_id=payload.assistant_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(assistant, JSONResponse):
        return assistant
    try:
        run = await compat_langgraph._create_run(
            runtime=runtime,
            actor=auth,
            thread_id=thread_id,
            payload=compat_langgraph.RunCreate.model_validate(payload.model_dump()),
            status="running",
        )
    except PolicyDeniedError as exc:
        return compat_langgraph._policy_denied(exc, x_request_id)
    runtime.run_store.mark_run_running(run["run_id"])
    runtime.replay_buffer.append(
        run["run_id"],
        None,
        AgentEvent(type="run.started", payload={"thread_id": thread_id}),
    )
    events = [_serialize_event(event) for event in runtime.replay_buffer.replay(run["run_id"])]
    return _wrap_result(
        operation="run.stream_probe",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
        stream_events=events,
    )


@router.post("/langgraph/threads/{thread_id}/runs/{run_id}/join", response_model=None)
def join_langgraph_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    run = compat_langgraph._lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    runtime.run_store.complete_run(run_id, output={"compat_status": "joined"})
    run["status"] = "succeeded"
    runtime.replay_buffer.append(
        run_id,
        None,
        AgentEvent(type="run.completed", payload={"compat_status": "joined"}),
    )
    compat_langgraph._record_run_action(
        runtime=runtime,
        actor=auth,
        action="compat.langgraph.run.join",
        run=run,
    )
    assistant = runtime.assistants.get(run["assistant_id"])
    return _wrap_result(
        operation="run.join",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
    )


@router.post("/langgraph/threads/{thread_id}/runs/{run_id}/cancel", response_model=None)
async def cancel_langgraph_run(
    thread_id: str,
    run_id: int,
    response: Response,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:invoke",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    run = compat_langgraph._lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    task_id = run["metadata"]["dimoorun_mapping"]["task_id"]
    runtime.run_store.cancel_run(run_id)
    await runtime.task_backend.cancel(task_id)
    run["status"] = "cancelled"
    runtime.replay_buffer.append(
        run_id,
        None,
        AgentEvent(type="run.cancelled", payload={"task_id": task_id}),
    )
    compat_langgraph._record_run_action(
        runtime=runtime,
        actor=auth,
        action="compat.langgraph.run.cancel",
        run=run,
    )
    assistant = runtime.assistants.get(run["assistant_id"])
    return _wrap_result(
        operation="run.cancel",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
    )


@router.post("/migration-report", response_model=None)
def migration_report(
    response: Response,
    payload: CompatibilityMigrationPayload,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    report = build_migration_report(payload.model_dump())
    golden = default_golden_runner().record(
        operation="migration.report",
        expected_semantics={
            "framework": payload.framework,
            "adapter": payload.adapter,
            "capabilities": payload.capabilities,
            "streaming_modes": payload.streaming_modes,
            "supports_last_event_id_replay": True,
        },
        compat_response=report,
        native_resources={
            "tenant_id": auth.tenant_id,
            "project_id": auth.project_id,
        },
        unsupported_capabilities=[
            item["capability"] for item in report["unsupported_capabilities"]
        ],
        divergence_reason=report["blocked_reason"]
        or (
            "compatibility_not_supported"
            if report["unsupported_capabilities"]
            else None
        ),
    )
    return {
        "report": report,
        "golden_record": golden,
        "request_id": x_request_id,
    }


def _assistant_resources(assistant: dict[str, Any] | None) -> dict[str, Any]:
    if not assistant:
        return {}
    mapping = dict(assistant.get("metadata", {}).get("dimoorun_mapping", {}))
    return {
        "assistant_id": assistant.get("assistant_id"),
        "deployment_id": mapping.get("deployment_id"),
        "agent_id": mapping.get("agent_id"),
        "agent_version_id": mapping.get("agent_version_id"),
        "tenant_id": mapping.get("tenant_id"),
        "project_id": mapping.get("project_id"),
    }


def _thread_resources(thread: dict[str, Any] | None) -> dict[str, Any]:
    if not thread:
        return {}
    mapping = dict(thread.get("metadata", {}).get("dimoorun_mapping", {}))
    return {
        "thread_id": thread.get("thread_id"),
        "checkpoint_thread_id": mapping.get("checkpoint_thread_id"),
        "tenant_id": mapping.get("tenant_id"),
        "project_id": mapping.get("project_id"),
    }


def _run_resources(run: dict[str, Any] | None, assistant: dict[str, Any] | None) -> dict[str, Any]:
    if not run:
        return {}
    run_mapping = dict(run.get("metadata", {}).get("dimoorun_mapping", {}))
    assistant_mapping = dict((assistant or {}).get("metadata", {}).get("dimoorun_mapping", {}))
    return {
        "run_id": run_mapping.get("run_id", run.get("run_id")),
        "task_id": run_mapping.get("task_id"),
        "thread_id": run.get("thread_id"),
        "assistant_id": run.get("assistant_id"),
        "deployment_id": assistant_mapping.get("deployment_id"),
        "agent_id": assistant_mapping.get("agent_id"),
        "agent_version_id": assistant_mapping.get("agent_version_id"),
    }


def _wrap_result(
    *,
    operation: str,
    compat_response: dict[str, Any],
    native_resources: dict[str, Any],
    stream_events: list[dict[str, Any]] | None = None,
    stream_status: dict[str, Any] | None = None,
    expected_semantics: dict[str, Any] | None = None,
    divergence_reason: str | None = None,
) -> dict[str, Any]:
    unsupported = _unsupported_capability_explanations(compat_response)
    record = default_golden_runner().record(
        operation=operation,
        expected_semantics=expected_semantics
        or _expected_semantics(
            operation=operation,
            compat_response=compat_response,
            native_resources=native_resources,
            stream_events=stream_events,
            stream_status=stream_status,
        ),
        compat_response=compat_response,
        native_resources=native_resources,
        unsupported_capabilities=[item["capability"] for item in unsupported],
        divergence_reason=divergence_reason,
    )
    result = {
        "operation": operation,
        "compat_response": compat_response,
        "native_resources": native_resources,
        "resource_links": _resource_links(native_resources),
        "unsupported_capability_explanations": unsupported,
        "divergence_reason": record["divergence_reason"],
        "golden_record": record,
    }
    if stream_events is not None:
        result["stream_events"] = stream_events
    if stream_status is not None:
        result["stream_status"] = stream_status
    return result


@router.get("/langgraph/threads/{thread_id}/runs/{run_id}/events", response_model=None)
def replay_langgraph_events(
    thread_id: str,
    run_id: int,
    response: Response,
    last_event_id: Annotated[str | None, Query()] = None,
    authorization: AuthorizationHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any] | JSONResponse:
    auth = _compat_actor(
        response=response,
        authorization=authorization,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        request_id=x_request_id,
        required_scope="agent:read",
    )
    if isinstance(auth, JSONResponse):
        return auth
    runtime = compat_langgraph.default_compat_runtime()
    thread = compat_langgraph._lookup_thread(
        runtime=runtime,
        thread_id=thread_id,
        actor=auth,
        request_id=x_request_id,
    )
    if isinstance(thread, JSONResponse):
        return thread
    run = compat_langgraph._lookup_run(
        runtime=runtime,
        thread_id=thread_id,
        run_id=run_id,
        request_id=x_request_id,
    )
    if isinstance(run, JSONResponse):
        return run
    assistant = runtime.assistants.get(run["assistant_id"])
    try:
        events = runtime.replay_buffer.replay(run_id, last_event_id)
    except ReplayExpiredError as exc:
        return error_response(
            status_code=409,
            error_code="stream_replay_expired",
            message="Last-Event-ID is no longer available in the replay buffer.",
            request_id=x_request_id,
            details={"event": _serialize_event(exc.event)},
        )
    return _wrap_result(
        operation="run.replay",
        compat_response=run,
        native_resources=_run_resources(run, assistant),
        stream_events=[_serialize_event(event) for event in events],
    )


def _resource_links(native_resources: dict[str, Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    deployment_id = native_resources.get("deployment_id")
    if deployment_id is not None:
        links.append(
            {
                "label": f"Deployment #{deployment_id}",
                "path": f"/deployments/{deployment_id}",
            }
        )
    run_id = native_resources.get("run_id")
    if run_id is not None:
        links.append({"label": f"Run #{run_id}", "path": f"/runs/{run_id}"})
    task_id = native_resources.get("task_id")
    if task_id is not None:
        links.append({"label": f"Task #{task_id}", "path": "/tasks"})
    agent_id = native_resources.get("agent_id")
    if agent_id is not None:
        links.append({"label": f"Agent #{agent_id}", "path": "/agents"})
    return links


def _unsupported_capability_explanations(
    compat_response: dict[str, Any],
) -> list[dict[str, Any]]:
    if compat_response.get("error_code") == "compatibility_not_supported":
        return [
            {
                "capability": str(compat_response.get("details", {}).get("feature", "unknown")),
                "reason": "compatibility_not_supported",
                "recommended_workaround": "Use native DimooRun runtime semantics for this feature.",
            }
        ]
    return []


def _serialize_event(event: AgentEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "sequence": event.sequence,
        "type": event.type,
        "payload": event.payload,
    }


def _expected_semantics(
    *,
    operation: str,
    compat_response: dict[str, Any],
    native_resources: dict[str, Any],
    stream_events: list[dict[str, Any]] | None,
    stream_status: dict[str, Any] | None,
) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "operation": operation,
        "compat_resource_type": operation.split(".", maxsplit=1)[0],
        "native_source_of_truth": ["run", "task", "event", "audit"],
    }
    if operation.startswith("assistant."):
        expected["sdk_shape"] = "langgraph.assistant"
        expected["assistant_id"] = compat_response.get("assistant_id")
    elif operation.startswith("thread."):
        expected["sdk_shape"] = "langgraph.thread"
        expected["thread_id"] = compat_response.get("thread_id")
    elif operation.startswith("run."):
        expected["sdk_shape"] = "langgraph.run"
        expected["thread_id"] = compat_response.get("thread_id")
        expected["assistant_id"] = compat_response.get("assistant_id")
        expected["compat_status"] = compat_response.get("status")
        expected["native_run_id"] = native_resources.get("run_id")
        expected["native_task_id"] = native_resources.get("task_id")
    if operation == "run.stream_probe":
        expected["stream_mode"] = "events"
        expected["event_types"] = [
            str(event["type"])
            for event in (stream_events or [])
            if event.get("type") is not None
        ]
    if operation == "run.stream_status":
        expected["supports_last_event_id_replay"] = True
        expected["latest_event_id"] = (stream_status or {}).get("latest_event_id")
        expected["replay_from_event_id"] = (stream_status or {}).get(
            "replay_from_event_id"
        )
    if operation == "run.replay":
        expected["supports_last_event_id_replay"] = True
        expected["replayed_event_types"] = [
            str(event["type"])
            for event in (stream_events or [])
            if event.get("type") is not None
        ]
    return expected
