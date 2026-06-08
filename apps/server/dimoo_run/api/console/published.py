from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from dimoo_run.api.dependencies import RequestIdHeader, enforce_console_actor
from dimoo_run.core.config import Settings
from dimoo_run.gateway.route_tester import (
    evidence_bundle_archive,
    evidence_bundle_catalog,
    evidence_bundle_export,
    request_log_detail,
    surface_detail,
    sync_state,
)

router = APIRouter(
    prefix="/v1/console",
    tags=["console-aggregate"],
    dependencies=[Depends(enforce_console_actor)],
)


@router.get("/published-surfaces/{surface_id}")
def get_published_surface_detail(
    surface_id: int,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    sync_state(Settings.from_env().database.url)
    return surface_detail(surface_id, request_id=x_request_id)


@router.get("/published-surfaces/{surface_id}/request-logs/{request_log_id}")
def get_published_surface_request_log(
    surface_id: int,
    request_log_id: int,
    x_request_id: RequestIdHeader = None,
) -> Any:
    sync_state(Settings.from_env().database.url)
    result = request_log_detail(surface_id, request_log_id, request_id=x_request_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "request_log_not_found",
                "message": "Request log was not found for this published surface.",
                "request_id": x_request_id,
            },
        )
    return result


@router.get("/published-surfaces/{surface_id}/evidence-bundles")
def list_published_surface_evidence_bundles(
    surface_id: int,
    x_request_id: RequestIdHeader = None,
) -> dict[str, Any]:
    sync_state(Settings.from_env().database.url)
    return evidence_bundle_catalog(surface_id, request_id=x_request_id)


@router.get("/published-surfaces/{surface_id}/evidence-bundles/{bundle_id}")
def export_published_surface_evidence_bundle(
    surface_id: int,
    bundle_id: str,
    x_request_id: RequestIdHeader = None,
) -> Any:
    sync_state(Settings.from_env().database.url)
    result = evidence_bundle_export(surface_id, bundle_id, request_id=x_request_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "evidence_bundle_not_found",
                "message": "Evidence bundle was not found for this published surface.",
                "request_id": x_request_id,
            },
        )
    return result


@router.post("/published-surfaces/{surface_id}/evidence-bundles/{bundle_id}/archive")
def archive_published_surface_evidence_bundle(
    surface_id: int,
    bundle_id: str,
    payload: dict[str, Any],
    x_request_id: RequestIdHeader = None,
) -> Any:
    sync_state(Settings.from_env().database.url)
    result = evidence_bundle_archive(
        surface_id,
        bundle_id,
        payload,
        request_id=x_request_id,
    )
    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "error_code": "evidence_bundle_not_found",
                "message": "Evidence bundle was not found for this published surface.",
                "request_id": x_request_id,
            },
        )
    return result
