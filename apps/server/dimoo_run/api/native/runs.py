from fastapi import APIRouter, Request, Response

from dimoo_run.api.dependencies import RequestIdHeader, not_implemented_response
from dimoo_run.domain.schemas import ErrorResponse

router = APIRouter(tags=["native-runs"])


@router.get("/runs/{run_id}", responses={501: {"model": ErrorResponse}})
def get_run(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/runs/{run_id}/events", responses={501: {"model": ErrorResponse}})
def list_run_events(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.get("/runs/{run_id}/attempts", responses={501: {"model": ErrorResponse}})
def list_run_attempts(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


def run_action_response(
    request: Request,
    response: Response,
    request_id: str | None,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, request_id, audit_required=True)
    response.status_code = status_code
    return error


@router.post("/runs/{run_id}/cancel", responses={501: {"model": ErrorResponse}})
def cancel_run(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return run_action_response(request, response, x_request_id)


@router.post("/runs/{run_id}/resume", responses={501: {"model": ErrorResponse}})
def resume_run(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return run_action_response(request, response, x_request_id)


@router.post("/runs/{run_id}/retry", responses={501: {"model": ErrorResponse}})
def retry_run(request: Request, response: Response, x_request_id: RequestIdHeader) -> ErrorResponse:
    return run_action_response(request, response, x_request_id)


@router.post("/runs/{run_id}/replay", responses={501: {"model": ErrorResponse}})
def replay_run(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return run_action_response(request, response, x_request_id)
