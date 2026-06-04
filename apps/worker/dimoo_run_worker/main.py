import argparse
import sys
import time
from pathlib import Path
from typing import Any

SERVER_SRC = Path(__file__).resolve().parents[2] / "server"
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))


def default_adapters() -> dict[str, Any]:
    from dimoo_run.adapters.deepagents.adapter import DeepAgentsAdapter
    from dimoo_run.adapters.langchain_agent.adapter import LangChainAgentAdapter
    from dimoo_run.adapters.langgraph.adapter import LangGraphAdapter

    return {
        "deepagents": DeepAgentsAdapter(),
        "langchain-agent": LangChainAgentAdapter(),
        "langchain": LangChainAgentAdapter(),
        "langgraph": LangGraphAdapter(),
    }


def run_once(*, adapters: dict[str, Any] | None = None) -> str:
    from dimoo_run.core.config import Settings
    from dimoo_run.persistence.database import create_session_factory
    from dimoo_run.worker.durable import execute_durable_once
    from dimoo_run.worker.loop import WorkerLoop

    settings = Settings.from_env()
    if settings.runtime.native_runtime_store == "sqlalchemy":
        session_factory = create_session_factory(settings.database.url)
        session = session_factory()

        async def execute_once(*, queue: str, lease_seconds: int) -> Any:
            return await execute_durable_once(
                session=session,
                worker_id="worker_cli",
                queue=queue,
                lease_seconds=lease_seconds,
                adapters=adapters or default_adapters(),
            )

        try:
            heartbeat = WorkerLoop(worker_id="worker_cli", execute_once=execute_once).run_once()
            session.commit()
            return heartbeat.status
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    heartbeat = WorkerLoop().run_once()
    return heartbeat.status


def run_forever(
    *,
    adapters: dict[str, Any] | None = None,
    poll_interval_seconds: float = 1.0,
) -> None:
    while True:
        status = run_once(adapters=adapters)
        print(f"DimooRun worker process ready ({status})", flush=True)
        time.sleep(poll_interval_seconds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dimoorun-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.once:
        status = run_once()
        print(f"DimooRun worker process ready ({status})")
        return
    run_forever(poll_interval_seconds=args.poll_interval)


if __name__ == "__main__":
    main()
