from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from dimoo_run.api.admin.datasets import dataset_items_for

PartialFailurePolicy = Literal["continue", "abort"]


@dataclass(frozen=True)
class BatchProgressSummary:
    total_items: int
    queued_items: int
    running_items: int
    retrying_items: int
    failed_items: int
    dead_letter_items: int
    cancelled_items: int
    completed_items: int
    terminal_items: int


def normalize_batch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "runtime-batch").strip() or "runtime-batch"
    deployment_id = int(payload.get("deployment_id") or 0)
    if deployment_id <= 0:
        raise ValueError("deployment_id_required")
    concurrency = int(payload.get("concurrency") or 1)
    if concurrency <= 0:
        raise ValueError("concurrency_invalid")
    retry_policy = dict(payload.get("retry_policy") or {})
    cancel_policy = str(payload.get("cancel_policy") or "queued_only")
    if cancel_policy not in {"queued_only", "best_effort"}:
        raise ValueError("cancel_policy_invalid")
    partial_failure_policy = str(payload.get("partial_failure_policy") or "continue")
    if partial_failure_policy not in {"continue", "abort"}:
        raise ValueError("partial_failure_policy_invalid")
    audit_reason = str(payload.get("audit_reason") or "").strip()
    if not audit_reason:
        raise ValueError("audit_reason_required")
    dataset_id = int(payload.get("dataset_id") or 0) or None
    input_items = payload.get("input_items")
    if bool(dataset_id) == bool(input_items):
        raise ValueError("batch_input_source_required")
    if dataset_id is not None:
        items = [
            dict(item.get("payload_preview", {}).get("input") or {})
            for item in dataset_items_for(dataset_id)
        ]
    else:
        if not isinstance(input_items, list) or not input_items:
            raise ValueError("input_items_invalid")
        items = list(input_items)
    return {
        "name": name,
        "deployment_id": deployment_id,
        "dataset_id": dataset_id,
        "input_items": items,
        "concurrency": concurrency,
        "retry_policy": retry_policy,
        "cancel_policy": cancel_policy,
        "partial_failure_policy": partial_failure_policy,
        "artifact_output_ref": _optional_string(payload.get("artifact_output_ref")),
        "audit_reason": audit_reason,
    }


def normalize_batch_items(
    items: list[Any],
    *,
    partial_failure_policy: PartialFailurePolicy,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            accepted.append(item)
            continue
        failed.append(
            {
                "index": index,
                "status": "failed",
                "error_code": "batch_item_invalid",
                "message": "Batch input item must be an object.",
                "input": item,
            }
        )
        if partial_failure_policy == "abort":
            raise ValueError("batch_item_invalid")
    return accepted, failed


def summarize_batch_items(items: list[dict[str, Any]]) -> BatchProgressSummary:
    counts = {
        "queued": 0,
        "running": 0,
        "retrying": 0,
        "failed": 0,
        "dead_letter": 0,
        "cancelled": 0,
        "completed": 0,
    }
    for item in items:
        status = str(item.get("status") or "queued")
        if status == "queued":
            counts["queued"] += 1
        elif status in {"leased", "running"}:
            counts["running"] += 1
        elif status == "retrying":
            counts["retrying"] += 1
        elif status == "failed":
            counts["failed"] += 1
        elif status == "dead_letter":
            counts["dead_letter"] += 1
        elif status == "cancelled":
            counts["cancelled"] += 1
        elif status in {"succeeded", "completed"}:
            counts["completed"] += 1
    terminal_items = (
        counts["failed"]
        + counts["dead_letter"]
        + counts["cancelled"]
        + counts["completed"]
    )
    return BatchProgressSummary(
        total_items=len(items),
        queued_items=counts["queued"],
        running_items=counts["running"],
        retrying_items=counts["retrying"],
        failed_items=counts["failed"],
        dead_letter_items=counts["dead_letter"],
        cancelled_items=counts["cancelled"],
        completed_items=counts["completed"],
        terminal_items=terminal_items,
    )


def overall_batch_status(summary: BatchProgressSummary) -> str:
    if summary.total_items == 0:
        return "empty"
    if summary.cancelled_items == summary.total_items:
        return "cancelled"
    if summary.failed_items + summary.dead_letter_items == summary.total_items:
        return "failed"
    if summary.completed_items == summary.total_items:
        return "completed"
    if summary.running_items > 0 or summary.retrying_items > 0:
        return "running"
    if summary.failed_items > 0 or summary.dead_letter_items > 0:
        return "partial_failed"
    return "queued"


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
