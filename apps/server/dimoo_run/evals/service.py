from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


class Evaluator(Protocol):
    name: str

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        trace: dict[str, Any],
        expected: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Experiment:
    id: str
    tenant_id: str
    project_id: str
    name: str
    agent_id: str
    baseline_agent_version_id: str | None
    candidate_agent_version_id: str
    dataset_id: str
    evaluator_config: dict[str, Any]
    status: str = "draft"


@dataclass(frozen=True)
class ExperimentRun:
    id: str
    experiment_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None


@dataclass(frozen=True)
class EvaluationResult:
    id: str
    tenant_id: str
    project_id: str
    experiment_run_id: str
    evaluator_name: str
    score: float
    passed: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityGateDecision:
    experiment_run_id: str
    allowed: bool
    failed_evaluators: list[str]


class ThresholdEvaluator:
    def __init__(self, *, name: str, passing_score: float) -> None:
        self.name = name
        self.passing_score = passing_score

    async def evaluate(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        trace: dict[str, Any],
        expected: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = input_data, trace, context
        score = 1.0 if expected is not None and output_data == expected else 0.0
        return {
            "score": score,
            "passed": score >= self.passing_score,
            "metadata": {"reason": "exact_match"},
        }


class InMemoryEvaluationService:
    def __init__(self) -> None:
        self.experiments: dict[str, Experiment] = {}
        self.experiment_runs: dict[str, ExperimentRun] = {}
        self.results: list[EvaluationResult] = []

    def create_experiment(
        self,
        *,
        tenant_id: str,
        project_id: str,
        name: str,
        agent_id: str,
        baseline_agent_version_id: str | None,
        candidate_agent_version_id: str,
        dataset_id: str,
        evaluator_config: dict[str, Any],
    ) -> Experiment:
        experiment = Experiment(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            agent_id=agent_id,
            baseline_agent_version_id=baseline_agent_version_id,
            candidate_agent_version_id=candidate_agent_version_id,
            dataset_id=dataset_id,
            evaluator_config=evaluator_config,
        )
        self.experiments[experiment.id] = experiment
        return experiment

    async def run_experiment(
        self,
        *,
        experiment_id: str,
        items: list[dict[str, Any]],
        evaluators: list[Evaluator],
    ) -> ExperimentRun:
        experiment = self.experiments[experiment_id]
        run = ExperimentRun(
            id=str(uuid4()),
            experiment_id=experiment_id,
            status="succeeded",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        self.experiment_runs[run.id] = run
        for item in items:
            for evaluator in evaluators:
                result = await evaluator.evaluate(
                    item["input_data"],
                    item["output_data"],
                    trace=item.get("trace", {}),
                    expected=item.get("expected"),
                )
                self.results.append(
                    EvaluationResult(
                        id=str(uuid4()),
                        tenant_id=experiment.tenant_id,
                        project_id=experiment.project_id,
                        experiment_run_id=run.id,
                        evaluator_name=evaluator.name,
                        score=float(result["score"]),
                        passed=bool(result["passed"]),
                        metadata=dict(result.get("metadata", {})),
                    )
                )
        return run

    def quality_gate(self, experiment_run_id: str) -> QualityGateDecision:
        failed = [
            result.evaluator_name
            for result in self.results
            if result.experiment_run_id == experiment_run_id and not result.passed
        ]
        return QualityGateDecision(
            experiment_run_id=experiment_run_id,
            allowed=not failed,
            failed_evaluators=failed,
        )
