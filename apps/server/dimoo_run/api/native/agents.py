from typing import Any

from fastapi import APIRouter, Request, Response

from dimoo_run.api.dependencies import (
    IdempotencyKeyHeader,
    RequestIdHeader,
    not_implemented_response,
)
from dimoo_run.domain.schemas import ErrorResponse

router = APIRouter(tags=["native-agents"])


@router.post("/agents", responses={501: {"model": ErrorResponse}})
def create_agent(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/agents")
def list_agents() -> list[dict[str, Any]]:
    return []


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict[str, str]:
    return {"id": agent_id}


@router.patch("/agents/{agent_id}", responses={501: {"model": ErrorResponse}})
def update_agent(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.delete("/agents/{agent_id}", responses={501: {"model": ErrorResponse}})
def delete_agent(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(
        request,
        x_request_id,
        audit_required=True,
        extra_details={"soft_delete_required": True},
    )
    response.status_code = status_code
    return error


@router.post("/agents/{agent_id}/versions", responses={501: {"model": ErrorResponse}})
def create_agent_version(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/agents/{agent_id}/versions")
def list_agent_versions(agent_id: str) -> list[dict[str, str]]:
    return []


@router.get("/agents/{agent_id}/versions/{version}")
def get_agent_version(agent_id: str, version: str) -> dict[str, str]:
    return {"agent_id": agent_id, "version": version}


@router.post("/agents/{agent_id}/invoke", responses={501: {"model": ErrorResponse}})
def invoke_agent(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> ErrorResponse:
    _ = idempotency_key
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.post("/agents/{agent_id}/tasks", responses={501: {"model": ErrorResponse}})
def create_agent_task(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> ErrorResponse:
    _ = idempotency_key
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.post("/agents/{agent_id}/stream", responses={501: {"model": ErrorResponse}})
def stream_agent(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
    idempotency_key: IdempotencyKeyHeader,
) -> ErrorResponse:
    _ = idempotency_key
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error
