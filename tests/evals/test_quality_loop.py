import pytest
from dimoo_run.datasets.service import DatasetScopeMismatchError, DatasetService
from dimoo_run.evals.service import (
    EvaluationResult,
    InMemoryEvaluationService,
    ThresholdEvaluator,
)


def test_dataset_item_can_be_created_from_failed_run_with_redaction() -> None:
    service = DatasetService(redacted_fields={"api_key"})
    dataset = service.create_dataset(
        tenant_id="tenant_1",
        project_id="project_1",
        name="failures",
        source="failure_case",
        schema={"type": "object"},
        created_by="user_1",
    )

    item = service.add_item_from_run(
        dataset_id=dataset.id,
        tenant_id="tenant_1",
        project_id="project_1",
        run_id="run_failed",
        input_data={"question": "hello", "request": {"api_key": "sk-secret"}},
        output_data={"answer": "bad"},
        expected={"answer": "good"},
        created_by="user_1",
    )

    assert item.dataset_id == dataset.id
    assert item.tenant_id == "tenant_1"
    assert item.project_id == "project_1"
    assert item.source_run_id == "run_failed"
    assert item.input_data["request"]["api_key"] == "[REDACTED]"


def test_dataset_item_rejects_missing_or_cross_scope_dataset() -> None:
    service = DatasetService()

    with pytest.raises(DatasetScopeMismatchError, match="dataset_not_found"):
        service.add_item_from_run(
            dataset_id="missing",
            tenant_id="tenant_1",
            project_id="project_1",
            run_id="run_failed",
            input_data={},
            output_data={},
            expected=None,
            created_by="user_1",
        )

    dataset = service.create_dataset(
        tenant_id="tenant_1",
        project_id="project_1",
        name="failures",
        source="failure_case",
        schema={"type": "object"},
        created_by="user_1",
    )

    with pytest.raises(DatasetScopeMismatchError, match="dataset_scope_mismatch"):
        service.add_item_from_run(
            dataset_id=dataset.id,
            tenant_id="tenant_2",
            project_id="project_2",
            run_id="run_failed",
            input_data={},
            output_data={},
            expected=None,
            created_by="user_2",
        )


async def test_experiment_run_generates_evaluation_results_and_quality_gate() -> None:
    service = InMemoryEvaluationService()
    experiment = service.create_experiment(
        tenant_id="tenant_1",
        project_id="project_1",
        name="candidate",
        agent_id="agent_1",
        baseline_agent_version_id="version_old",
        candidate_agent_version_id="version_new",
        dataset_id="dataset_1",
        evaluator_config={"min_score": 0.8},
    )

    experiment_run = await service.run_experiment(
        experiment_id=experiment.id,
        items=[
            {
                "input_data": {"question": "hello"},
                "output_data": {"answer": "hello"},
                "expected": {"answer": "hello"},
            }
        ],
        evaluators=[ThresholdEvaluator(name="exact_match", passing_score=1.0)],
    )

    assert experiment_run.experiment_id == experiment.id
    assert service.results[0] == EvaluationResult(
        id=service.results[0].id,
        tenant_id="tenant_1",
        project_id="project_1",
        experiment_run_id=experiment_run.id,
        evaluator_name="exact_match",
        score=1.0,
        passed=True,
        metadata={"reason": "exact_match"},
    )
    assert service.quality_gate(experiment_run.id).allowed is True
