import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from dimoo_run.domain.models import Run, RunAttempt
from dimoo_run.runtime.run_manager import RuntimeAttempt, RuntimeRun
from dimoo_run.runtime.state_machine import assert_run_attempt_transition, assert_run_transition


class SQLAlchemyRunStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    @property
    def runs(self) -> dict[int, RuntimeRun]:
        return {
            run.id: _run_from_model(run)
            for run in self.session.scalars(select(Run).where(Run.is_deleted.is_(False)))
        }

    @property
    def attempts(self) -> dict[int, RuntimeAttempt]:
        return {
            attempt.id: _attempt_from_model(attempt)
            for attempt in self.session.scalars(
                select(RunAttempt).where(RunAttempt.is_deleted.is_(False))
            )
        }

    async def create_run(
        self,
        *,
        tenant_id: int,
        project_id: int,
        agent_id: int,
        agent_version_id: int,
        deployment_id: int | None,
        input_data: dict[str, Any],
        override_config: dict[str, Any] | None = None,
        thread_id: str | None = None,
        run_id: int | None = None,
    ) -> RuntimeRun:
        _ = override_config, run_id
        run = Run(
            tenant_id=tenant_id,
            project_id=project_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            deployment_id=deployment_id,
            thread_id=thread_id,
            input_ref=_encode_ref(input_data),
        )
        self.session.add(run)
        self.session.flush()
        return _run_from_model(run)

    async def create_attempt(
        self,
        *,
        run_id: int,
        task_id: int,
        worker_id: str,
    ) -> RuntimeAttempt:
        latest_attempt = self.session.scalar(
            select(RunAttempt)
            .where(RunAttempt.run_id == run_id)
            .order_by(RunAttempt.attempt_no.desc())
        )
        attempt_no = latest_attempt.attempt_no + 1 if latest_attempt is not None else 1
        attempt = RunAttempt(
            run_id=run_id,
            task_id=task_id,
            attempt_no=attempt_no,
            worker_id=worker_id,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.session.add(attempt)
        run = self._run_model(run_id)
        if run.status != "running":
            assert_run_transition(run.status, "running")
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
        self.session.flush()
        return _attempt_from_model(attempt)

    def get_run(self, run_id: int) -> RuntimeRun:
        return _run_from_model(self._run_model(run_id))

    def complete_run(self, run_id: int, output: dict[str, Any]) -> None:
        run = self._run_model(run_id)
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
        assert_run_transition(run.status, "succeeded")
        run.status = "succeeded"
        run.output_ref = _encode_ref(output)
        run.finished_at = datetime.now(UTC)
        self.session.flush()

    def fail_run(self, run_id: int, error: dict[str, Any]) -> None:
        run = self._run_model(run_id)
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
        assert_run_transition(run.status, "failed")
        run.status = "failed"
        run.error = _error_message(error)
        run.finished_at = datetime.now(UTC)
        self.session.flush()

    def timeout_run(self, run_id: int, error: dict[str, Any]) -> None:
        run = self._run_model(run_id)
        if run.status == "pending":
            assert_run_transition(run.status, "running")
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
        assert_run_transition(run.status, "timeout")
        run.status = "timeout"
        run.error = _error_message(error)
        run.finished_at = datetime.now(UTC)
        self.session.flush()

    def mark_run_running(self, run_id: int) -> None:
        run = self._run_model(run_id)
        if run.status == "running":
            return
        assert_run_transition(run.status, "running")
        run.status = "running"
        run.started_at = run.started_at or datetime.now(UTC)
        self.session.flush()

    def cancel_run(self, run_id: int) -> None:
        run = self._run_model(run_id)
        assert_run_transition(run.status, "cancelled")
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        self.session.flush()

    def delete_run(self, run_id: int) -> None:
        run = self._run_model(run_id)
        run.is_deleted = True
        run.deleted_at = datetime.now(UTC)
        self.session.flush()

    def complete_attempt(self, attempt_id: int) -> None:
        attempt = self._attempt_model(attempt_id)
        assert_run_attempt_transition(attempt.status, "succeeded")
        attempt.status = "succeeded"
        attempt.finished_at = datetime.now(UTC)
        attempt.latency_ms = _latency_ms(attempt.started_at, attempt.finished_at)
        self.session.flush()

    def fail_attempt(self, attempt_id: int, error: dict[str, Any]) -> None:
        attempt = self._attempt_model(attempt_id)
        assert_run_attempt_transition(attempt.status, "failed")
        attempt.status = "failed"
        attempt.error = _error_message(error)
        attempt.finished_at = datetime.now(UTC)
        attempt.latency_ms = _latency_ms(attempt.started_at, attempt.finished_at)
        self.session.flush()

    def timeout_attempt(self, attempt_id: int, error: dict[str, Any]) -> None:
        attempt = self._attempt_model(attempt_id)
        assert_run_attempt_transition(attempt.status, "timeout")
        attempt.status = "timeout"
        attempt.error = _error_message(error)
        attempt.finished_at = datetime.now(UTC)
        attempt.latency_ms = _latency_ms(attempt.started_at, attempt.finished_at)
        self.session.flush()

    def _run_model(self, run_id: int) -> Run:
        run = self.session.get(Run, run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def _attempt_model(self, attempt_id: int) -> RunAttempt:
        attempt = self.session.get(RunAttempt, attempt_id)
        if attempt is None:
            raise KeyError(attempt_id)
        return attempt


def _run_from_model(run: Run) -> RuntimeRun:
    return RuntimeRun(
        run_id=run.id,
        tenant_id=run.tenant_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
        agent_version_id=run.agent_version_id,
        deployment_id=run.deployment_id,
        input_data=_decode_ref(run.input_ref),
        status=run.status,
        thread_id=run.thread_id,
        output=_decode_ref(run.output_ref),
        error={"message": run.error} if run.error else None,
        created_at=run.created_at,
    )


def _attempt_from_model(attempt: RunAttempt) -> RuntimeAttempt:
    return RuntimeAttempt(
        attempt_id=attempt.id,
        run_id=attempt.run_id,
        task_id=attempt.task_id or "",
        worker_id=attempt.worker_id or "",
        attempt_no=attempt.attempt_no,
        status=attempt.status,
        started_at=attempt.started_at or attempt.created_at,
        finished_at=attempt.finished_at,
        error={"message": attempt.error} if attempt.error else None,
    )


def _encode_ref(payload: dict[str, Any]) -> str:
    return "json:" + json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _decode_ref(value: str | None) -> dict[str, Any]:
    if not value or not value.startswith("json:"):
        return {}
    payload = json.loads(value.removeprefix("json:"))
    return payload if isinstance(payload, dict) else {}


def _error_message(error: dict[str, Any]) -> str:
    message = error.get("message")
    return str(message if message is not None else error)


def _latency_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    if started_at is None or finished_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    return max(0, int((finished_at - started_at).total_seconds() * 1000))
