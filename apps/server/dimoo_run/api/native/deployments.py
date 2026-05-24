from fastapi import APIRouter, Request, Response

from dimoo_run.api.dependencies import RequestIdHeader, not_implemented_response
from dimoo_run.domain.schemas import ErrorResponse

router = APIRouter(tags=["native-deployments"])


@router.get("/deployments", responses={501: {"model": ErrorResponse}})
def list_deployments(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/deployments/{deployment_id}", responses={501: {"model": ErrorResponse}})
def get_deployment(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/deployments/{deployment_id}/instances", responses={501: {"model": ErrorResponse}})
def list_deployment_instances(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


def control_response(request: Request, response: Response, request_id: str | None) -> ErrorResponse:
    error, status_code = not_implemented_response(
        request,
        request_id,
        audit_required=True,
    )
    response.status_code = status_code
    return error


@router.post("/deployments/{deployment_id}/activate", responses={501: {"model": ErrorResponse}})
def activate_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)


@router.post("/deployments/{deployment_id}/pause", responses={501: {"model": ErrorResponse}})
def pause_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)


@router.post("/deployments/{deployment_id}/resume", responses={501: {"model": ErrorResponse}})
def resume_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)


@router.post("/deployments/{deployment_id}/drain", responses={501: {"model": ErrorResponse}})
def drain_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)


@router.post("/deployments/{deployment_id}/stop", responses={501: {"model": ErrorResponse}})
def stop_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)


@router.post("/deployments/{deployment_id}/restart", responses={501: {"model": ErrorResponse}})
def restart_deployment(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return control_response(request, response, x_request_id)
