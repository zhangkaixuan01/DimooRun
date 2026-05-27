import os
import sys

from dimoo_run.ops.init_db import run as init_db


def main() -> None:
    if os.getenv("DIMOORUN_SKIP_DB_INIT", "false").lower() != "true":
        init_db()
    command = sys.argv[1:] or [
        "uvicorn",
        "dimoo_run.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
