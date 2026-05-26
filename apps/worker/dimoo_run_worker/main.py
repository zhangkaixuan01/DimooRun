import sys
from pathlib import Path

SERVER_SRC = Path(__file__).resolve().parents[2] / "server"
if str(SERVER_SRC) not in sys.path:
    sys.path.insert(0, str(SERVER_SRC))


def main() -> None:
    from dimoo_run.worker.loop import WorkerLoop

    heartbeat = WorkerLoop().run_once()
    print(f"DimooRun worker process ready ({heartbeat.status})")


if __name__ == "__main__":
    main()
