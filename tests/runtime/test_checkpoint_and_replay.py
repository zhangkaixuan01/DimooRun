from dimoo_run.checkpoints.index import CheckpointIndexStore
from dimoo_run.replay.scheduler import ReplayScheduler
from dimoo_run.runtime.run_manager import InMemoryRunStore
from dimoo_run.scheduler.in_memory import InMemoryTaskBackend


def test_checkpoint_index_stores_lookup_metadata_without_payload_parsing() -> None:
    store = CheckpointIndexStore()

    checkpoint = store.add(
        run_id=1,
        thread_id="thread_1",
        checkpoint_id="checkpoint_1",
        payload_uri="framework://checkpoint/1",
        checkpoint_ns="default",
    )

    assert checkpoint.payload_uri == "framework://checkpoint/1"
    assert store.list_by_run("run_1") == [checkpoint]


def test_checkpoint_index_created_at_uses_fresh_timestamp() -> None:
    store = CheckpointIndexStore()

    first = store.add(
        run_id=1,
        thread_id="thread_1",
        checkpoint_id="checkpoint_1",
        payload_uri="framework://checkpoint/1",
    )
    second = store.add(
        run_id=1,
        thread_id="thread_1",
        checkpoint_id="checkpoint_2",
        payload_uri="framework://checkpoint/2",
    )

    assert first.created_at is not second.created_at


async def test_replay_scheduler_creates_new_run_and_task() -> None:
    run_store = InMemoryRunStore()
    task_backend = InMemoryTaskBackend()
    scheduler = ReplayScheduler(run_store=run_store, task_backend=task_backend)
    source_run = await run_store.create_run(
        tenant_id=1,
        project_id=1,
        agent_id=1,
        agent_version_id="version_1",
        deployment_id=1,
        input_data={"message": "hello"},
    )

    replay_run = await scheduler.replay_run(
        source_run_id=source_run.run_id,
        candidate_agent_version_id="version_2",
    )

    assert replay_run.run_id != source_run.run_id
    assert replay_run.input_data == source_run.input_data
    assert replay_run.agent_version_id == "version_2"
    assert len(task_backend.tasks) == 1
