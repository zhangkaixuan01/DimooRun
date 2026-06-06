from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Response, status

from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
    error_response,
)
from dimoo_run.api.native.dependencies import get_native_runtime
from dimoo_run.api.native.runtime import NativeRuntimeStore, SQLAlchemyNativeRuntimeStore

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]
NativeRuntimeDep = Annotated[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    Depends(get_native_runtime),
]

_STATE_DATABASE_URL: str | None = None
_DATASET_SEQUENCE = 20
_DATASET_ITEM_SEQUENCE = 300
_DATASETS: dict[tuple[str, int | None, int | None, str], dict[str, Any]] = {}
_DATASET_ITEMS_BY_RUN: dict[tuple[str, int | None, int | None, int, int], dict[str, Any]] = {}
_DATASET_ITEMS_BY_DATASET: dict[int, list[dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def reset_quality_datasets() -> None:
    global _STATE_DATABASE_URL, _DATASET_SEQUENCE, _DATASET_ITEM_SEQUENCE
    _STATE_DATABASE_URL = None
    _DATASET_SEQUENCE = 20
    _DATASET_ITEM_SEQUENCE = 300
    _DATASETS.clear()
    _DATASET_ITEMS_BY_RUN.clear()
    _DATASET_ITEMS_BY_DATASET.clear()


def _sync_state() -> str:
    global _STATE_DATABASE_URL
    from dimoo_run.core.config import Settings

    database_url = Settings.from_env().database.url
    if _STATE_DATABASE_URL != database_url:
        reset_quality_datasets()
        _STATE_DATABASE_URL = database_url
    return database_url


def _next_dataset_id() -> int:
    global _DATASET_SEQUENCE
    _DATASET_SEQUENCE += 1
    return _DATASET_SEQUENCE


def _next_dataset_item_id() -> int:
    global _DATASET_ITEM_SEQUENCE
    _DATASET_ITEM_SEQUENCE += 1
    return _DATASET_ITEM_SEQUENCE


def _redact(value: Any, fields: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in fields else _redact(item, fields)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, fields) for item in value]
    return value


def _dataset_for(
    *,
    database_url: str,
    tenant_id: int | None,
    project_id: int | None,
    dataset_name: str,
) -> dict[str, Any]:
    key = (database_url, tenant_id, project_id, dataset_name)
    dataset = _DATASETS.get(key)
    if dataset is None:
        dataset = {
            "id": _next_dataset_id(),
            "name": dataset_name,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "source": "run_capture",
            "created_at": _now(),
        }
        _DATASETS[key] = dataset
    return dataset


def dataset_items_for(dataset_id: int) -> list[dict[str, Any]]:
    _sync_state()
    return list(_DATASET_ITEMS_BY_DATASET.get(dataset_id, []))


@router.post("/v1/datasets/capture-run", status_code=status.HTTP_201_CREATED)
def capture_run_to_dataset(
    response: Response,
    runtime: NativeRuntimeDep,
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    data = payload or {}
    dataset_name = str(data.get("dataset_name") or "").strip()
    source_run_id = int(data.get("source_run_id") or 0)
    if not dataset_name or source_run_id <= 0 or x_tenant_id is None or x_project_id is None:
        return error_response(
            status_code=400,
            error_code="invalid_dataset_capture",
            message="Dataset name and source run are required.",
            request_id=x_request_id,
            details={
                "required_fields": [
                    "dataset_name",
                    "source_run_id",
                    "X-Tenant-Id",
                    "X-Project-Id",
                ]
            },
        )
    run = runtime.get_run(source_run_id, tenant_id=x_tenant_id, project_id=x_project_id)
    if run is None:
        return error_response(
            status_code=404,
            error_code="run_not_found",
            message="Source run was not found.",
            request_id=x_request_id,
            details={"source_run_id": source_run_id},
        )

    database_url = _sync_state()
    dataset = _dataset_for(
        database_url=database_url,
        tenant_id=x_tenant_id,
        project_id=x_project_id,
        dataset_name=dataset_name,
    )
    duplicate_key = (database_url, x_tenant_id, x_project_id, dataset["id"], source_run_id)
    existing = _DATASET_ITEMS_BY_RUN.get(duplicate_key)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return {**existing, "duplicate": True, "request_id": x_request_id}

    redact_fields = {
        str(field)
        for field in data.get("redact_fields", [])
        if isinstance(field, str) and field.strip()
    }
    payload_preview = {
        "input": _redact(getattr(run, "input", {}) or {}, redact_fields),
        "output": _redact(getattr(run, "output", None), redact_fields),
        "error": _redact(getattr(run, "error", None), redact_fields),
    }
    item = {
        "dataset_id": dataset["id"],
        "dataset_name": dataset["name"],
        "dataset_item_id": _next_dataset_item_id(),
        "source_run_id": source_run_id,
        "label": data.get("label"),
        "input_ref": f"run:{source_run_id}:input",
        "output_ref": f"run:{source_run_id}:output",
        "expected_ref": data.get("expected_ref"),
        "payload_preview": payload_preview,
        "redaction": {"fields": sorted(redact_fields)},
        "provenance": {
            "source_run_id": source_run_id,
            "dataset_id": dataset["id"],
            "captured_at": _now(),
            "environment": x_environment,
        },
        "audit": {
            "action": "dataset.capture_run",
            "resource_type": "dataset",
            "resource_id": dataset["id"],
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "duplicate": False,
    }
    _DATASET_ITEMS_BY_RUN[duplicate_key] = item
    _DATASET_ITEMS_BY_DATASET.setdefault(dataset["id"], []).append(item)
    return {**item, "request_id": x_request_id}
