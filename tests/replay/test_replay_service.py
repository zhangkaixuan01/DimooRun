import pytest
from dimoo_run.replay.service import InMemoryReplayService, ReplaySourceRun


async def test_replay_job_creates_new_run_without_mutating_source_run() -> None:
    created_runs: list[dict[str, object]] = []

    async def create_run_task(**kwargs):  # type: ignore[no-untyped-def]
        created_runs.append(kwargs)
        return {"run_id": "run_replay_1"}, "task_replay_1"

    source = ReplaySourceRun(
        run_id="run_failed",
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id="version_old",
        deployment_id=1,
        input_ref="artifact://input",
        input_data={"question": "hello"},
        status="failed",
    )
    service = InMemoryReplayService(create_run_task=create_run_task)

    job = await service.create_replay_job(
        source_run=source,
        candidate_agent_version_id="version_new",
        requested_by="user_1",
        override_config={"temperature": 0},
    )

    assert job.source_run_id == "run_failed"
    assert job.replay_run_id == "run_replay_1"
    assert job.replay_task_id == "task_replay_1"
    assert source.status == "failed"
    assert created_runs[0]["agent_version_id"] == "version_new"
    assert created_runs[0]["input_data"] == {"question": "hello"}
    assert created_runs[0]["override_config"] == {"temperature": 0}


async def test_replay_rejects_replay_of_running_source_run() -> None:
    service = InMemoryReplayService(create_run_task=None)

    with pytest.raises(PermissionError, match="source_run_not_terminal"):
        await service.create_replay_job(
            source_run=ReplaySourceRun(
                run_id="run_running",
                tenant_id=1,
                project_id=1,
                agent_id=1,
                agent_version_id="version_old",
                deployment_id=1,
                input_ref=None,
                input_data={},
                status="running",
            ),
            candidate_agent_version_id="version_new",
            requested_by="user_1",
        )
