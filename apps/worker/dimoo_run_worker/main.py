import argparse
import signal
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
    from dimoo_run.core.config import Settings
    from dimoo_run.persistence.database import create_session_factory
    from dimoo_run.runtime.capacity import WorkerRegistry
    from dimoo_run.worker.durable import execute_durable_once
    from dimoo_run.worker.loop import WorkerLoop

    settings = Settings.from_env()
    if settings.runtime.native_runtime_store == "sqlalchemy":
        session_factory = create_session_factory(settings.database.url)
        session = session_factory()
        worker_registry = WorkerRegistry(database_url=settings.database.url)

        async def durable_execute_once(*, queue: str, lease_seconds: int) -> Any:
            return await execute_durable_once(
                session=session,
                worker_id="worker_cli",
                queue=queue,
                lease_seconds=lease_seconds,
                adapters=adapters or default_adapters(),
            )

        loop = WorkerLoop(
            worker_id="worker_cli",
            poll_interval_seconds=poll_interval_seconds,
            execute_once=durable_execute_once,
            worker_registry=worker_registry,
        )
    else:
        session = None
        loop = WorkerLoop(
            worker_id="worker_cli",
            poll_interval_seconds=poll_interval_seconds,
        )

    def request_shutdown(*_: object) -> None:
        loop.request_shutdown(graceful=True)

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        while not loop.stopped:
            heartbeat = loop.run_once()
            print(f"DimooRun worker process ready ({heartbeat.status})", flush=True)
            if not loop.stopped:
                time.sleep(poll_interval_seconds)
        if session is not None:
            session.commit()
    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        if session is not None:
            session.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dimoorun-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.once:
        status = run_once()
        display_status = "idle" if status == "idle" else f"{status}; idle"
        print(f"DimooRun worker process ready ({display_status})")
        return
    run_forever(poll_interval_seconds=args.poll_interval)


if __name__ == "__main__":
    main()
