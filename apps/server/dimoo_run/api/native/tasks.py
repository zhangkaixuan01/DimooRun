from fastapi import APIRouter, Request, Response

from dimoo_run.api.dependencies import RequestIdHeader, not_implemented_response
from dimoo_run.domain.schemas import ErrorResponse

router = APIRouter(tags=["native-tasks"])


@router.get("/tasks/{task_id}", responses={501: {"model": ErrorResponse}})
def get_task(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id)
    response.status_code = status_code
    return error


@router.post("/tasks/{task_id}/cancel", responses={501: {"model": ErrorResponse}})
def cancel_task(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, x_request_id, audit_required=True)
    response.status_code = status_code
    return error
