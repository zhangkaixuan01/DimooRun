from pathlib import Path
from typing import Any

from dimoo_run.cli.main import run_cli
from dimoo_run.config.project import load_project_config, validate_project_workspace


def test_init_creates_workspace_config_and_validate_accepts_it(tmp_path: Path) -> None:
    exit_code = run_cli(["init", "--path", str(tmp_path), "--name", "support-agent"])

    assert exit_code == 0
    assert (tmp_path / "dimoorun.yaml").exists()
    assert (tmp_path / "agents" / "support-agent" / "manifest.yaml").exists()

    config = load_project_config(tmp_path / "dimoorun.yaml")
    assert config.project.name == "support-agent"
    assert config.adapters.langgraph.enabled is True

    assert run_cli(["validate", "--path", str(tmp_path)]) == 0
    assert validate_project_workspace(tmp_path) == []


def test_validate_rejects_bad_manifest_entrypoint(tmp_path: Path) -> None:
    run_cli(["init", "--path", str(tmp_path), "--name", "support-agent"])
    manifest_path = tmp_path / "agents" / "support-agent" / "manifest.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "agent:create_agent",
            "agent",
        ),
        encoding="utf-8",
    )

    assert run_cli(["validate", "--path", str(tmp_path)]) == 1


def test_validate_rejects_manifest_entrypoint_that_cannot_be_resolved(tmp_path: Path) -> None:
    run_cli(["init", "--path", str(tmp_path), "--name", "support-agent"])
    manifest_path = tmp_path / "agents" / "support-agent" / "manifest.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "agent:create_agent",
            "runtime.entrypoint:create_agent",
        ),
        encoding="utf-8",
    )

    errors = validate_project_workspace(tmp_path)

    assert any("entrypoint module file was not found" in error for error in errors)


def test_doctor_reports_fixed_langchain_ecosystem_matrix(capsys: Any) -> None:
    exit_code = run_cli(["doctor"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "langchain==1.3.1" in captured.out
    assert "langchain-core==1.4.0" in captured.out
    assert "langgraph==1.2.1" in captured.out
    assert "deepagents==0.6.3" in captured.out
    assert "langsmith==0.8.5" in captured.out


def test_production_phase_commands_fail_until_phase_10_is_implemented(capsys: Any) -> None:
    exit_code = run_cli(["up"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "production foundation phase 10" in captured.out


def test_cli_migrate_langgraph_generates_report(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "agent.py").write_text("def create_agent():\n    return object()\n", encoding="utf-8")
    output = tmp_path / "out"

    exit_code = run_cli(
        [
            "migrate",
            "langgraph",
            str(source),
            "--output",
            str(output),
            "--name",
            "support-agent",
        ]
    )

    assert exit_code == 0
    assert (output / "manifest.yaml").exists()
    assert (output / "dimoorun.yaml").exists()
    assert (output / "migration_report.md").exists()


def test_cli_migrate_aegra_generates_source_specific_report(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "agent.py").write_text("def create_agent():\n    return object()\n", encoding="utf-8")
    output = tmp_path / "out"

    exit_code = run_cli(
        [
            "migrate",
            "aegra",
            str(source),
            "--output",
            str(output),
            "--name",
            "support-agent",
        ]
    )

    assert exit_code == 0
    assert "source type: aegra" in (output / "migration_report.md").read_text(encoding="utf-8")
