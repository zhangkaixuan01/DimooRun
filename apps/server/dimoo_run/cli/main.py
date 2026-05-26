from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dimoo_run.config.project import validate_project_workspace, write_default_workspace
from dimoo_run.migration.aegra import migrate_aegra_project
from dimoo_run.migration.langgraph import migrate_langgraph_project
from dimoo_run.migration.langgraph_platform import migrate_langgraph_platform_project

LANGCHAIN_VERSION_MATRIX = {
    "langchain": "1.3.1",
    "langchain-core": "1.4.0",
    "langgraph": "1.2.1",
    "deepagents": "0.6.3",
    "langsmith": "0.8.5",
}

PRODUCTION_PHASE_COMMANDS = {"dev", "worker", "up", "down"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dimoorun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--path", default=".")
    init_parser.add_argument("--name", default="support-agent")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--path", default=".")

    subparsers.add_parser("doctor")
    subparsers.add_parser("dev")
    subparsers.add_parser("worker")
    subparsers.add_parser("up")
    subparsers.add_parser("down")
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

    if args.command in PRODUCTION_PHASE_COMMANDS:
        print(
            f"{args.command} is reserved for production foundation phase 10 "
            "and is not implemented yet."
        )
        return 2

    print(f"{args.command} is registered but not implemented yet")
    return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
