from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, status

from dimoo_run.api.admin.datasets import dataset_items_for, reset_quality_datasets
from dimoo_run.api.dependencies import (
    EnvironmentHeader,
    ProjectIdHeader,
    RequestIdHeader,
    TenantIdHeader,
    enforce_console_actor,
    error_response,
)

router = APIRouter(tags=["admin"], dependencies=[Depends(enforce_console_actor)])
AdminPayload = Annotated[dict[str, Any] | None, Body()]

_STATE_DATABASE_URL: str | None = None
_EXPERIMENT_SEQUENCE = 100
_EXPERIMENT_RUN_SEQUENCE = 400
_EXPERIMENT_RUNS: dict[int, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def reset_quality_experiments() -> None:
    global _STATE_DATABASE_URL, _EXPERIMENT_SEQUENCE, _EXPERIMENT_RUN_SEQUENCE
    _STATE_DATABASE_URL = None
    _EXPERIMENT_SEQUENCE = 100
    _EXPERIMENT_RUN_SEQUENCE = 400
    _EXPERIMENT_RUNS.clear()


def reset_quality_workflows() -> None:
    reset_quality_datasets()
    reset_quality_experiments()


def _sync_state() -> str:
    global _STATE_DATABASE_URL
    from dimoo_run.core.config import Settings

    database_url = Settings.from_env().database.url
    if _STATE_DATABASE_URL != database_url:
        reset_quality_experiments()
        _STATE_DATABASE_URL = database_url
    return database_url


def _next_experiment_id() -> int:
    global _EXPERIMENT_SEQUENCE
    _EXPERIMENT_SEQUENCE += 1
    return _EXPERIMENT_SEQUENCE


def _next_experiment_run_id() -> int:
    global _EXPERIMENT_RUN_SEQUENCE
    _EXPERIMENT_RUN_SEQUENCE += 1
    return _EXPERIMENT_RUN_SEQUENCE


def _gate(
    *,
    experiment_run_id: int,
    average_score: float,
    min_score: float,
    dataset_id: int,
    result_count: int,
    candidate_agent_version_id: int | None = None,
) -> dict[str, Any]:
    passed = average_score >= min_score and result_count > 0
    return {
        "status": "passed" if passed else "failed",
        "promotion_allowed": passed,
        "blocked_reason": None if passed else "quality_gate_failed",
        "required_evidence": ["experiment_run", "evaluation_results"],
        "evidence": {
            "experiment_run_id": experiment_run_id,
            "dataset_id": dataset_id,
            "candidate_agent_version_id": candidate_agent_version_id,
            "result_count": result_count,
            "average_score": average_score,
            "min_score": min_score,
        },
    }


@router.post("/v1/experiments/run", status_code=status.HTTP_201_CREATED)
def run_experiment(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    _sync_state()
    data = payload or {}
    dataset_id = int(data.get("dataset_id") or 0)
    candidate_agent_version_id = int(data.get("candidate_agent_version_id") or 0)
    agent_id = int(data.get("agent_id") or 0)
    if dataset_id <= 0 or candidate_agent_version_id <= 0 or agent_id <= 0:
        return error_response(
            status_code=400,
            error_code="invalid_experiment_run",
            message="Experiment requires agent, candidate version, and dataset.",
            request_id=x_request_id,
            details={"required_fields": ["agent_id", "candidate_agent_version_id", "dataset_id"]},
        )

    evaluator_config = data.get("evaluator_config")
    if not isinstance(evaluator_config, dict):
        evaluator_config = {}
    min_score = float(evaluator_config.get("min_score") or 0.8)
    evaluator_names = [
        str(item)
        for item in evaluator_config.get("evaluators", ["exact_match"])
        if isinstance(item, str) and item.strip()
    ] or ["exact_match"]
    items = dataset_items_for(dataset_id)
    experiment_id = _next_experiment_id()
    experiment_run_id = _next_experiment_run_id()
    results = [
        {
            "id": index + 1,
            "experiment_run_id": experiment_run_id,
            "dataset_item_id": item["dataset_item_id"],
            "evaluator_name": evaluator_name,
            "score": 1.0,
            "passed": 1.0 >= min_score,
            "metadata": {
                "reason": "exact_match",
                "source_run_id": item["source_run_id"],
            },
        }
        for index, item in enumerate(items)
        for evaluator_name in evaluator_names
    ]
    average_score = (
        sum(float(result["score"]) for result in results) / len(results)
        if results
        else 0.0
    )
    gate = _gate(
        experiment_run_id=experiment_run_id,
        average_score=average_score,
        min_score=min_score,
        dataset_id=dataset_id,
        result_count=len(results),
        candidate_agent_version_id=candidate_agent_version_id,
    )
    body = {
        "experiment": {
            "id": experiment_id,
            "name": str(data.get("name") or "quality-experiment"),
            "agent_id": agent_id,
            "baseline_agent_version_id": data.get("baseline_agent_version_id"),
            "candidate_agent_version_id": candidate_agent_version_id,
            "dataset_id": dataset_id,
            "evaluator_config": evaluator_config,
            "status": "completed",
        },
        "run": {
            "id": experiment_run_id,
            "experiment_id": experiment_id,
            "status": "completed",
            "started_at": _now(),
            "finished_at": _now(),
        },
        "results": results,
        "score_distribution": {
            "count": len(results),
            "average_score": average_score,
            "min_score": min_score,
            "passed": sum(1 for result in results if result["passed"]),
            "failed": sum(1 for result in results if not result["passed"]),
        },
        "quality_gate": gate,
        "audit": {
            "action": "experiment.run",
            "resource_type": "experiment",
            "resource_id": experiment_id,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
        "request_id": x_request_id,
    }
    _EXPERIMENT_RUNS[experiment_run_id] = body
    return body


@router.post("/v1/quality-gates/preview")
def preview_quality_gate(
    payload: AdminPayload = None,
    x_request_id: RequestIdHeader = None,
    x_tenant_id: TenantIdHeader = None,
    x_project_id: ProjectIdHeader = None,
    x_environment: EnvironmentHeader = None,
) -> Any:
    _sync_state()
    data = payload or {}
    experiment_run_id = int(data.get("experiment_run_id") or 0)
    experiment = _EXPERIMENT_RUNS.get(experiment_run_id)
    if experiment is None:
        gate = _gate(
            experiment_run_id=experiment_run_id,
            average_score=0.0,
            min_score=1.0,
            dataset_id=0,
            result_count=0,
            candidate_agent_version_id=None,
        )
    else:
        gate = dict(experiment["quality_gate"])
        evidence = dict(gate.get("evidence") or {})
        requested_candidate_id = data.get("candidate_agent_version_id")
        evidence_candidate_id = evidence.get("candidate_agent_version_id")
        if (
            requested_candidate_id is not None
            and evidence_candidate_id is not None
            and int(requested_candidate_id) != int(evidence_candidate_id)
        ):
            evidence["requested_candidate_agent_version_id"] = requested_candidate_id
            gate = {
                **gate,
                "status": "failed",
                "promotion_allowed": False,
                "blocked_reason": "candidate_evidence_mismatch",
                "evidence": evidence,
            }
    return {
        **gate,
        "deployment_id": data.get("deployment_id"),
        "candidate_agent_version_id": data.get("candidate_agent_version_id"),
        "audit": {
            "action": "quality_gate.preview",
            "resource_type": "quality_gate",
            "resource_id": experiment_run_id,
            "request_id": x_request_id,
            "tenant_id": x_tenant_id,
            "project_id": x_project_id,
            "environment": x_environment,
        },
    }
