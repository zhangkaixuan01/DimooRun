import subprocess
import sys
from pathlib import Path
from typing import Any

from dimoo_run.core.context import RuntimeContext
from dimoo_run.core.events import AgentResult
from dimoo_run.domain.models import Agent, AgentVersion, Run, Task
from dimoo_run.persistence.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def add_project_root_to_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)


class FakeEntrypointAdapter:
    framework = "fake"

    async def load(
        self,
        package_uri: str,
        manifest: dict[str, Any],
        runtime_config: dict[str, Any],
    ) -> dict[str, Any]:
        return {"package_uri": package_uri, "manifest": manifest}

    async def invoke(
        self,
        agent: Any,
        input_data: dict[str, Any],
        context: RuntimeContext,
    ) -> AgentResult:
        _ = agent, context
        return AgentResult(output={"message": input_data["message"]})


def test_worker_entrypoint_exposes_one_shot_mode() -> None:
    add_project_root_to_path()
    from apps.worker.dimoo_run_worker import main

    assert hasattr(main, "run_once")


def test_worker_entrypoint_default_adapters_include_langgraph() -> None:
    add_project_root_to_path()
    from apps.worker.dimoo_run_worker import main

    adapters = main.default_adapters()

    assert "langgraph" in adapters
    assert adapters["langgraph"].framework == "langgraph"


def test_worker_entrypoint_run_once_executes_sqlalchemy_task(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    database_url = f"sqlite:///{tmp_path / 'worker-entrypoint.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    session = Session(engine)
    agent = Agent(tenant_id=1, project_id=1, name="support")
    session.add(agent)
    session.flush()
    version = AgentVersion(
        agent_id=agent.id,
        version="0.1.0",
        package_uri="memory://support",
        framework="fake",
        adapter="fake",
        entrypoint="agent:create",
        manifest_json={"runtime": {"entrypoint": "agent:create"}},
        capabilities_json={},
    )
    session.add(version)
    session.flush()
    run = Run(
        tenant_id=1,
        project_id=1,
        agent_id=agent.id,
        agent_version_id=version.id,
        input_ref='json:{"message":"hello"}',
    )
    session.add(run)
    session.flush()
    task = Task(run_id=run.id, tenant_id=1, project_id=1)
    session.add(task)
    session.commit()

    add_project_root_to_path()
    from apps.worker.dimoo_run_worker import main

    status = main.run_once(adapters={"fake": FakeEntrypointAdapter()})

    session.refresh(run)
    session.refresh(task)
    assert status == "executed"
    assert run.status == "succeeded"
    assert run.output_ref == 'json:{"message":"hello"}'
    assert task.status == "succeeded"


def test_worker_entrypoint_default_main_uses_forever_mode(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    add_project_root_to_path()
    from apps.worker.dimoo_run_worker import main

    calls: list[float] = []

    def fake_run_forever(*, poll_interval_seconds: float = 1.0) -> None:
        calls.append(poll_interval_seconds)

    monkeypatch.setattr(main, "run_forever", fake_run_forever)

    main.main([])

    assert calls == [1.0]


def test_worker_entrypoint_prints_ready_message() -> None:
    project_root = Path(__file__).resolve().parents[2]
    worker_entrypoint = project_root / "apps" / "worker" / "dimoo_run_worker" / "main.py"

    result = subprocess.run(
        [sys.executable, str(worker_entrypoint), "--once"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip().startswith("DimooRun worker process ready")
    assert "idle" in result.stdout
