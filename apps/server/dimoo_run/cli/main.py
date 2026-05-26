from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dimoo_run.cli.compose import run_compose
from dimoo_run.cli.dev import run_dev
from dimoo_run.config.project import validate_project_workspace, write_default_workspace
from dimoo_run.migration.aegra import migrate_aegra_project
from dimoo_run.migration.langgraph import migrate_langgraph_project
from dimoo_run.migration.langgraph_platform import migrate_langgraph_platform_project
from dimoo_run.worker.loop import WorkerLoop

LANGCHAIN_VERSION_MATRIX = {
    "langchain": "1.3.1",
    "langchain-core": "1.4.0",
    "langgraph": "1.2.1",
    "deepagents": "0.6.3",
    "langsmith": "0.8.5",
}

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dimoorun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--path", default=".")
    init_parser.add_argument("--name", default="support-agent")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--path", default=".")

    subparsers.add_parser("doctor")
    dev_parser = subparsers.add_parser("dev")
    dev_parser.add_argument("--dry-run", action="store_true")
    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--once", action="store_true")
    for command_name in ("up", "down", "logs"):
        compose_parser = subparsers.add_parser(command_name)
        compose_parser.add_argument("--dry-run", action="store_true")
    migrate_parser = subparsers.add_parser("migrate")
    migrate_subparsers = migrate_parser.add_subparsers(dest="migration_source", required=True)
    for source_name in ("langgraph", "aegra", "langgraph-platform"):
        source_parser = migrate_subparsers.add_parser(source_name)
        source_parser.add_argument("source")
        source_parser.add_argument("--output", required=True)
        source_parser.add_argument("--name", required=True)
    return parser


def _installed_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not installed"


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        write_default_workspace(Path(args.path), name=args.name)
        print(f"Initialized DimooRun workspace at {Path(args.path)}")
        return 0
    if args.command == "validate":
        errors = validate_project_workspace(Path(args.path))
        if errors:
            for error in errors:
                print(error)
            return 1
        print("DimooRun workspace is valid")
        return 0
    if args.command == "doctor":
        print("DimooRun doctor")
        for package_name, expected in LANGCHAIN_VERSION_MATRIX.items():
            print(f"{package_name}=={expected} installed={_installed_version(package_name)}")
        return 0
    if args.command == "dev":
        return run_dev(dry_run=args.dry_run)
    if args.command in {"up", "down", "logs"}:
        return run_compose(args.command, dry_run=args.dry_run).return_code
    if args.command == "worker":
        loop = WorkerLoop()
        if args.once:
            heartbeat = loop.run_once()
            print(f"{heartbeat.worker_id} {heartbeat.status}")
            return 0
        loop.run_forever()
        return 0
    if args.command == "migrate":
        migrations = {
            "langgraph": migrate_langgraph_project,
            "aegra": migrate_aegra_project,
            "langgraph-platform": migrate_langgraph_platform_project,
        }
        report = migrations[args.migration_source](
            Path(args.source),
            Path(args.output),
            project_name=args.name,
        )
        print(f"Migration report written to {report.report_path}")
        return 0

    print(f"{args.command} is registered but not implemented yet")
    return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
