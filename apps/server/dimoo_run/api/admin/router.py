
from fastapi import APIRouter, Request, Response

from dimoo_run.api.dependencies import RequestIdHeader, not_implemented_response
from dimoo_run.domain.schemas import ErrorResponse

router = APIRouter(tags=["admin"])


def admin_read_response(
    request: Request,
    response: Response,
    request_id: str | None,
) -> ErrorResponse:
    error, status_code = not_implemented_response(request, request_id)
    response.status_code = status_code
    return error


def admin_write_response(
    request: Request,
    response: Response,
    request_id: str | None,
    *,
    audit_required: bool = True,
) -> ErrorResponse:
    error, status_code = not_implemented_response(
        request,
        request_id,
        audit_required=audit_required,
    )
    response.status_code = status_code
    return error


@router.get("/policies", responses={501: {"model": ErrorResponse}})
def list_policies(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return admin_read_response(request, response, x_request_id)


@router.post("/policies", responses={501: {"model": ErrorResponse}})
def create_policy(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return admin_write_response(request, response, x_request_id)


@router.get("/artifacts/{artifact_id}", responses={501: {"model": ErrorResponse}})
def get_artifact(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return admin_read_response(request, response, x_request_id)


@router.get("/human-tasks", responses={501: {"model": ErrorResponse}})
def list_human_tasks(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return admin_read_response(request, response, x_request_id)


@router.post("/human-tasks/{task_id}/approve", responses={501: {"model": ErrorResponse}})
def approve_human_task(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return admin_write_response(request, response, x_request_id)


@router.post("/human-tasks/{task_id}/reject", responses={501: {"model": ErrorResponse}})
def reject_human_task(
    request: Request, response: Response, x_request_id: RequestIdHeader
) -> ErrorResponse:
    return admin_write_response(request, response, x_request_id)


def register_collection_routes(path: str) -> None:
    async def get_items(
        request: Request,
        response: Response,
        x_request_id: RequestIdHeader,
    ) -> ErrorResponse:
        return admin_read_response(request, response, x_request_id)

    async def create_item(
        request: Request, response: Response, x_request_id: RequestIdHeader
    ) -> ErrorResponse:
        return admin_write_response(request, response, x_request_id)

    router.add_api_route(
        path,
        get_items,
        methods=["GET"],
        responses={501: {"model": ErrorResponse}},
    )
    router.add_api_route(
        path,
        create_item,
        methods=["POST"],
        responses={501: {"model": ErrorResponse}},
    )


for _path in [
    "/model-gateways",
    "/published-surfaces",
    "/ingress-routes",
    "/datasets",
    "/experiments",
    "/service-accounts",
    "/schedules",
    "/batch-runs",
    "/notifications/channels",
    "/alerts/rules",
    "/backups/plans",
]:
    register_collection_routes(_path)


@router.get("/catalog/items", responses={501: {"model": ErrorResponse}})
def list_catalog_items(
    request: Request,
    response: Response,
    x_request_id: RequestIdHeader,
) -> ErrorResponse:
    return admin_read_response(request, response, x_request_id)
