import shutil
from pathlib import Path

from dimoo_run.migration.aegra import migrate_aegra_project
from dimoo_run.migration.langgraph import migrate_langgraph_project
from dimoo_run.migration.langgraph_platform import migrate_langgraph_platform_project


def test_langgraph_migration_generates_manifest_project_config_and_report(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "agent.py").write_text(
        "def create_agent():\n    return object()\n",
        encoding="utf-8",
    )

    output = tmp_path / "out"
    report = migrate_langgraph_project(source, output, project_name="support-agent")

    assert (output / "manifest.yaml").exists()
    assert (output / "dimoorun.yaml").exists()
    assert (output / "migration_report.md").exists()
    assert report.manifest_path == output / "manifest.yaml"
    assert "checkpoint migration is best-effort" in report.warnings


def test_langgraph_migration_reports_checkpoint_incompatibility(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "agent.py").write_text("def create_agent():\n    return object()\n", encoding="utf-8")
    (source / "checkpoint.sqlite").write_text("opaque", encoding="utf-8")

    report = migrate_langgraph_project(source, tmp_path / "out", project_name="support-agent")

    assert "checkpoint_incompatible" in report.compatibility_warnings


def test_langgraph_migration_reads_langgraph_json_and_reports_detected_capabilities(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "graph.py").write_text("def build_graph():\n    return object()\n", encoding="utf-8")
    (source / "langgraph.json").write_text(
        '{"graphs": {"support": "./graph.py:build_graph"}, "env": ".env"}',
        encoding="utf-8",
    )
    (source / "pyproject.toml").write_text(
        '[project]\ndependencies = ["langgraph-checkpoint-postgres", "langchain-openai"]\n',
        encoding="utf-8",
    )
    output = tmp_path / "out"

    report = migrate_langgraph_project(source, output, project_name="support-agent")

    assert report.detected_entrypoint == "graph:build_graph"
    report_text = (output / "migration_report.md").read_text(encoding="utf-8")
    assert "langgraph.json" in report_text
    assert "checkpoint backend: langgraph-checkpoint-postgres" in report_text
    assert "env file: .env" in report_text


def test_langgraph_migration_reports_multiple_graphs_for_manual_selection(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "support.py").write_text("def graph():\n    return object()\n", encoding="utf-8")
    (source / "billing.py").write_text("def graph():\n    return object()\n", encoding="utf-8")
    (source / "langgraph.json").write_text(
        '{"graphs": {"support": "./support.py:graph", "billing": "./billing.py:graph"}}',
        encoding="utf-8",
    )

    report = migrate_langgraph_project(source, tmp_path / "out", project_name="support-agent")

    report_text = report.report_path.read_text(encoding="utf-8")
    assert report.detected_entrypoint == "support:graph"
    assert "multiple_graphs_detected" in report.compatibility_warnings
    assert "support -> support:graph" in report_text
    assert "billing -> billing:graph" in report_text


def test_aegra_migration_report_declares_source_specific_limitations(tmp_path: Path) -> None:
    source = tmp_path / "aegra"
    source.mkdir()
    (source / "agent.py").write_text("def create_agent():\n    return object()\n", encoding="utf-8")

    report = migrate_aegra_project(source, tmp_path / "out", project_name="support-agent")

    report_text = report.report_path.read_text(encoding="utf-8")
    assert report.source_type == "aegra"
    assert "source type: aegra" in report_text
    assert "aegra custom routes require manual review" in report_text


def test_langgraph_platform_migration_report_declares_source_specific_limitations(
    tmp_path: Path,
) -> None:
    source = tmp_path / "platform"
    source.mkdir()
    (source / "langgraph.json").write_text(
        '{"graphs": {"support": "./agent.py:create_agent"}}',
        encoding="utf-8",
    )
    (source / "agent.py").write_text("def create_agent():\n    return object()\n", encoding="utf-8")

    report = migrate_langgraph_platform_project(
        source,
        tmp_path / "out",
        project_name="support-agent",
    )

    report_text = report.report_path.read_text(encoding="utf-8")
    assert report.source_type == "langgraph-platform"
    assert "source type: langgraph-platform" in report_text
    assert "hosted deployment settings require manual review" in report_text


def test_langgraph_compatibility_example_migrates_to_dimoorun_manifest() -> None:
    source = Path("examples/compatibility/langgraph-basic/source")
    output = source.parent / ".generated"
    if output.exists():
        shutil.rmtree(output)

    report = migrate_langgraph_project(source, output, project_name="compatibility-basic")

    assert report.detected_entrypoint == "agent:build_graph"
    assert (output / "manifest.yaml").exists()
    assert (output / "dimoorun.yaml").exists()
    report_text = (output / "migration_report.md").read_text(encoding="utf-8")
    assert "langgraph.json" in report_text
    assert "support -> agent:build_graph" in report_text
