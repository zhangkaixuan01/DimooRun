import json
from pathlib import Path
from typing import Any

import dimoo_run.cli.main as cli_main
import dimoo_run.core.config as core_config
from dimoo_run.config.project import load_project_config, validate_project_workspace

run_cli = cli_main.run_cli


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


def test_doctor_production_reports_invalid_runtime_settings(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(core_config, "_find_dotenv", lambda: None)
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/dimoorun.db")
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "memory")
    monkeypatch.setenv("OBJECT_STORE_BACKEND", "local")
    monkeypatch.setenv("OBJECT_STORE_ACCESS_KEY", "dimoorun")
    monkeypatch.setenv("OBJECT_STORE_SECRET_KEY", "dimoorun-dev-secret")
    monkeypatch.setenv("DIMOORUN_CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "memory")
    monkeypatch.setenv("DIMOORUN_DEV_API_KEY", "dev-key")

    exit_code = run_cli(["doctor", "production"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Production mode cannot use SQLite." in captured.out
    assert "Production mode requires a configured secret provider." in captured.out


def test_doctor_production_accepts_safe_runtime_settings(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(core_config, "_find_dotenv", lambda: None)
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example/dimoorun")
    monkeypatch.setenv("DIMOORUN_NATIVE_RUNTIME_STORE", "sqlalchemy")
    monkeypatch.setenv("OBJECT_STORE_BACKEND", "s3")
    monkeypatch.setenv("OBJECT_STORE_ACCESS_KEY", "prod-access")
    monkeypatch.setenv("OBJECT_STORE_SECRET_KEY", "prod-secret")
    monkeypatch.setenv("DIMOORUN_CORS_ORIGINS", "https://console.example.com")
    monkeypatch.setenv("DIMOORUN_SECRET_PROVIDER", "vault")
    monkeypatch.delenv("DIMOORUN_DEV_API_KEY", raising=False)

    exit_code = run_cli(["doctor", "production"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Production settings are valid" in captured.out


def test_compose_commands_support_dry_run(capsys: Any) -> None:
    exit_code = run_cli(["up", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "docker compose up -d" in captured.out


def test_dev_command_supports_dry_run(capsys: Any) -> None:
    exit_code = run_cli(["dev", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "server: uv run uvicorn dimoo_run.server:app" in captured.out
    assert "worker: uv run dimoorun worker" in captured.out
    assert "console: npm run dev" in captured.out


def test_worker_command_can_run_once(capsys: Any) -> None:
    exit_code = run_cli(["worker", "--once"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "idle" in captured.out


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


class FakeNativeAPIClient:
    last_instance: "FakeNativeAPIClient | None" = None

    def __init__(self, **_: object) -> None:
        type(self).last_instance = self
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._run_polls = 0

    def close(self) -> None:
        self.calls.append(("close", {}))

    def validate_package(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("validate_package", kwargs))
        return {"ready": True, "validation_token": "tok_cli"}

    def create_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_agent", kwargs))
        return {"id": 11, "name": kwargs["name"]}

    def create_agent_version(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_agent_version", kwargs))
        return {"id": 21, "status": "ready"}

    def create_deployment(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_deployment", kwargs))
        return {
            "id": 24,
            "desired_status": kwargs["desired_status"],
            "environment": kwargs["environment"],
        }

    def submit_deployment_task(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("submit_deployment_task", kwargs))
        return {"run_id": 31, "task_id": 41, "status": "queued"}

    def get_run(self, run_id: int) -> dict[str, Any]:
        self.calls.append(("get_run", {"run_id": run_id}))
        self._run_polls += 1
        status = "running" if self._run_polls == 1 else "succeeded"
        return {"id": run_id, "status": status, "started_at": None, "finished_at": None}

    def list_run_events(self, run_id: int) -> list[dict[str, Any]]:
        self.calls.append(("list_run_events", {"run_id": run_id}))
        return [{"sequence": 1, "type": "run.started"}]

    def replay_run(self, run_id: int, *, agent_version_id: int | None) -> dict[str, Any]:
        self.calls.append(
            ("replay_run", {"run_id": run_id, "agent_version_id": agent_version_id})
        )
        return {"id": 99, "status": "pending"}


def test_cli_package_validate_calls_native_api_client(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)

    exit_code = run_cli(
        [
            "package",
            "validate",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--package-uri",
            "oci://registry.example/support",
            "--framework",
            "langgraph",
            "--adapter",
            "langgraph",
            "--entrypoint",
            "agent:create_agent",
            "--secret-ref",
            "secret://model",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"validation_token": "tok_cli"' in captured.out
    assert FakeNativeAPIClient.last_instance is not None
    assert FakeNativeAPIClient.last_instance.calls[0][0] == "validate_package"


def test_cli_agent_publish_validates_package_then_creates_ready_version(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"runtime": {"entrypoint": "agent:create_agent"}}),
        encoding="utf-8",
    )

    exit_code = run_cli(
        [
            "agent",
            "publish",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--name",
            "support-agent",
            "--version",
            "1.0.0",
            "--package-uri",
            "oci://registry.example/support",
            "--framework",
            "langgraph",
            "--adapter",
            "langgraph",
            "--entrypoint",
            "agent:create_agent",
            "--manifest-file",
            str(manifest_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status": "ready"' in captured.out
    assert FakeNativeAPIClient.last_instance is not None
    calls = FakeNativeAPIClient.last_instance.calls
    assert [call[0] for call in calls[:3]] == [
        "validate_package",
        "create_agent",
        "create_agent_version",
    ]
    assert calls[2][1]["manifest"]["validation_token"] == "tok_cli"


def test_cli_deployment_task_submit_watch_and_replay_commands(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    monkeypatch.setattr(cli_main, "sleep", lambda _seconds: None)

    submit_exit = run_cli(
        [
            "deployment",
            "task",
            "submit",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--deployment-id",
            "33",
            "--input-json",
            '{"message":"hello"}',
            "--thread-id",
            "thread_cli",
        ]
    )
    watch_exit = run_cli(
        [
            "run",
            "watch",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--run-id",
            "31",
            "--poll-interval",
            "0",
            "--max-polls",
            "2",
            "--show-events",
        ]
    )
    replay_exit = run_cli(
        [
            "run",
            "replay",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--run-id",
            "31",
            "--agent-version-id",
            "44",
        ]
    )

    captured = capsys.readouterr()
    assert submit_exit == 0
    assert watch_exit == 0
    assert replay_exit == 0
    assert '"task_id": 41' in captured.out
    assert '"status": "succeeded"' in captured.out
    assert '"id": 99' in captured.out


def test_cli_deployment_create_calls_native_api_client(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"traffic": "stable"}), encoding="utf-8")

    exit_code = run_cli(
        [
            "deployment",
            "create",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--agent-id",
            "11",
            "--agent-version-id",
            "21",
            "--target-environment",
            "production",
            "--desired-status",
            "active",
            "--replicas",
            "3",
            "--config-file",
            str(config_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"desired_status": "active"' in captured.out
    assert FakeNativeAPIClient.last_instance is not None
    assert FakeNativeAPIClient.last_instance.calls[0] == (
        "create_deployment",
        {
            "agent_id": 11,
            "agent_version_id": 21,
            "environment": "production",
            "desired_status": "active",
            "replicas": 3,
            "config": {"traffic": "stable"},
        },
    )
