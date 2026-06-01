from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


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
    id: int
    tenant_id: int
    project_id: int
    name: str
    agent_id: int
    baseline_agent_version_id: int | None
    candidate_agent_version_id: int
    dataset_id: int
    evaluator_config: dict[str, Any]
    status: str = "draft"


@dataclass(frozen=True)
class ExperimentRun:
    id: int
    experiment_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None


@dataclass(frozen=True)
class EvaluationResult:
    id: int
    tenant_id: int
    project_id: int
    experiment_run_id: int
    evaluator_name: str
    score: float
    passed: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityGateDecision:
    experiment_run_id: int
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
        self.experiments: dict[int, Experiment] = {}
        self.experiment_runs: dict[int, ExperimentRun] = {}
        self.results: list[EvaluationResult] = []
        self._next_experiment_id = 1
        self._next_run_id = 1
        self._next_result_id = 1

    def create_experiment(
        self,
        *,
        tenant_id: int,
        project_id: int,
        name: str,
        agent_id: int,
        baseline_agent_version_id: int | None,
        candidate_agent_version_id: int,
        dataset_id: int,
        evaluator_config: dict[str, Any],
    ) -> Experiment:
        experiment = Experiment(
            id=self._next_experiment_id,
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            agent_id=agent_id,
            baseline_agent_version_id=baseline_agent_version_id,
            candidate_agent_version_id=candidate_agent_version_id,
            dataset_id=dataset_id,
            evaluator_config=evaluator_config,
        )
        self._next_experiment_id += 1
        self.experiments[experiment.id] = experiment
        return experiment

    async def run_experiment(
        self,
        *,
        experiment_id: int,
        items: list[dict[str, Any]],
        evaluators: list[Evaluator],
    ) -> ExperimentRun:
        experiment = self.experiments[experiment_id]
        run = ExperimentRun(
            id=self._next_run_id,
            experiment_id=experiment_id,
            status="succeeded",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        self._next_run_id += 1
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
                        id=self._next_result_id,
                        tenant_id=experiment.tenant_id,
                        project_id=experiment.project_id,
                        experiment_run_id=run.id,
                        evaluator_name=evaluator.name,
                        score=float(result["score"]),
                        passed=bool(result["passed"]),
                        metadata=dict(result.get("metadata", {})),
                    )
                )
                self._next_result_id += 1
        return run

    def quality_gate(self, experiment_run_id: int) -> QualityGateDecision:
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
