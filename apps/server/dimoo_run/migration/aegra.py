from pathlib import Path

from dimoo_run.migration.langgraph import MigrationReport, migrate_langgraph_project


def migrate_aegra_project(
    source_path: str | Path,
    output_path: str | Path,
    *,
    project_name: str,
) -> MigrationReport:
    return migrate_langgraph_project(
        source_path,
        output_path,
        project_name=project_name,
        source_type="aegra",
        source_warnings=[
            "aegra custom routes require manual review",
            "agent protocol extensions require manual review",
        ],
    )
