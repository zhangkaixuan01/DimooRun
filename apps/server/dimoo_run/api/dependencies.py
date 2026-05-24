from typing import Annotated, Any

from fastapi import Header, Request

from dimoo_run.domain.schemas import ErrorResponse

RequestIdHeader = Annotated[str | None, Header(alias="X-Request-Id")]
IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]


def not_implemented_response(
    request: Request,
    request_id: str | None,
    *,
    audit_required: bool = False,
    extra_details: dict[str, Any] | None = None,
) -> tuple[ErrorResponse, int]:
    details: dict[str, Any] = {"path": request.url.path}
    if audit_required:
        details["audit_required"] = True
    if extra_details:
        details.update(extra_details)
    return (
        ErrorResponse(
            error_code="not_implemented",
            message="This API contract is registered but not implemented yet.",
            request_id=request_id,
            details=details,
        ),
        501,
    )
