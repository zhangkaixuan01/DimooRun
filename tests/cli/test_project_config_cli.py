import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import dimoo_run.cli.main as cli_main
import dimoo_run.core.config as core_config
from dimoo_run.api.dependencies import default_api_key_authenticator, reset_api_key_authenticator
from dimoo_run.api.native.runtime import (
    SQLAlchemyNativeRuntimeStore,
    reset_native_runtime,
    set_default_native_runtime,
)
from dimoo_run.config.project import load_project_config, validate_project_workspace
from dimoo_run.persistence.database import Base
from dimoo_run.server import create_app
from fastapi.testclient import TestClient
from pytest import MonkeyPatch, fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

run_cli = cli_main.run_cli


@fixture()
def cli_native_api(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> Iterator[tuple[str, TestClient, Session]]:
    monkeypatch.setenv("DIMOORUN_RUNTIME_MODE", "dev")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    reset_api_key_authenticator()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    set_default_native_runtime(SQLAlchemyNativeRuntimeStore(session))
    authenticator = default_api_key_authenticator()
    scopes = {"agent:read", "agent:write", "agent:invoke", "agent:deploy"}
    service_account = authenticator.service_accounts.create(
        tenant_id=1,
        project_id=1,
        name="cli-first-run",
        permissions=scopes,
        created_by="admin_1",
    )
    api_key, _ = authenticator.create_key(
        tenant_id=1,
        project_id=1,
        name="cli-first-run-key",
        owner_type="service_account",
        owner_id=service_account.id,
        scopes=scopes,
        created_by="admin_1",
    )
    test_client = TestClient(create_app())

    def handler(request: httpx.Request) -> httpx.Response:
        response = test_client.request(
            request.method,
            request.url.raw_path.decode("utf-8"),
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )

    class NativeAPIClientWithTestTransport(cli_main.NativeAPIClient):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(cli_main, "NativeAPIClient", NativeAPIClientWithTestTransport)
    try:
        yield api_key, test_client, session
    finally:
        reset_native_runtime()
        reset_api_key_authenticator()
        session.close()


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
    monkeypatch.delenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    exit_code = run_cli(["doctor", "production"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Production mode cannot use SQLite." in captured.out
    assert "Production mode requires a configured secret provider." in captured.out
    assert (
        "Production mode requires an explicit non-default "
        "DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD."
    ) in captured.out


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
    monkeypatch.setenv("DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD", "ProdOnly-ChangeMe-123!")
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
    seed_agents: list[dict[str, Any]] = []
    seed_versions: dict[int, list[dict[str, Any]]] = {}
    seed_deployments: list[dict[str, Any]] = []

    def __init__(self, **_: object) -> None:
        type(self).last_instance = self
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._run_polls = 0
        self.agents = [dict(item) for item in type(self).seed_agents]
        self.versions = {
            agent_id: [dict(item) for item in versions]
            for agent_id, versions in type(self).seed_versions.items()
        }
        self.deployments = [dict(item) for item in type(self).seed_deployments]

    def close(self) -> None:
        self.calls.append(("close", {}))

    def validate_package(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("validate_package", kwargs))
        return {"ready": True, "validation_token": "tok_cli"}

    def create_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_agent", kwargs))
        agent = {"id": 11, "name": kwargs["name"], "status": "active"}
        self.agents.append(agent)
        return agent

    def list_agents(self) -> list[dict[str, Any]]:
        self.calls.append(("list_agents", {}))
        return self.agents

    def create_agent_version(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_agent_version", kwargs))
        version = {
            "id": 21,
            "agent_id": kwargs["agent_id"],
            "version": kwargs["version"],
            "status": "ready",
        }
        self.versions.setdefault(kwargs["agent_id"], []).append(version)
        return version

    def list_agent_versions(self, agent_id: int) -> list[dict[str, Any]]:
        self.calls.append(("list_agent_versions", {"agent_id": agent_id}))
        return self.versions.get(agent_id, [])

    def create_deployment(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("create_deployment", kwargs))
        deployment = {
            "id": 24,
            "agent_id": kwargs["agent_id"],
            "agent_version_id": kwargs["agent_version_id"],
            "desired_status": kwargs["desired_status"],
            "environment": kwargs["environment"],
        }
        self.deployments.append(deployment)
        return deployment

    def list_deployments(self) -> list[dict[str, Any]]:
        self.calls.append(("list_deployments", {}))
        return self.deployments

    def submit_deployment_task(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("submit_deployment_task", kwargs))
        return {"run_id": 31, "task_id": 41, "status": "queued"}

    def get_run(self, run_id: int) -> dict[str, Any]:
        self.calls.append(("get_run", {"run_id": run_id}))
        self._run_polls += 1
        status = "running" if self._run_polls == 1 else "succeeded"
        return {
            "id": run_id,
            "status": status,
            "deployment_id": 33,
            "agent_version_id": 44,
            "error": {"message": "provider timeout"} if run_id == 31 else None,
            "started_at": None,
            "finished_at": None,
        }

    def list_run_events(self, run_id: int) -> list[dict[str, Any]]:
        self.calls.append(("list_run_events", {"run_id": run_id}))
        return [{"sequence": 1, "type": "run.started"}]

    def get_run_integration_evidence(self, run_id: int) -> dict[str, Any]:
        self.calls.append(("get_run_integration_evidence", {"run_id": run_id}))
        return {
            "run_id": run_id,
            "trace_links": [{"provider": "langfuse", "url": "https://langfuse.example.test/trace/31"}],
            "exporters": [{"provider": "opentelemetry", "status": "delivered"}],
            "model_gateway": [{"provider": "litellm", "model": "gpt-4.1-mini"}],
            "failures": [],
            "records": [],
        }

    def replay_run(self, run_id: int, *, agent_version_id: int | None) -> dict[str, Any]:
        self.calls.append(
            ("replay_run", {"run_id": run_id, "agent_version_id": agent_version_id})
        )
        return {"id": 99, "status": "pending"}

    def rollback_deployment(
        self,
        *,
        deployment_id: int,
        expected_current_version_id: int,
        rollback_agent_version_id: int | None,
        rollback_reason: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "rollback_deployment",
                {
                    "deployment_id": deployment_id,
                    "expected_current_version_id": expected_current_version_id,
                    "rollback_agent_version_id": rollback_agent_version_id,
                    "rollback_reason": rollback_reason,
                },
            )
        )
        return {"id": deployment_id, "agent_version_id": rollback_agent_version_id, "status": "active"}

    def decide_human_task(self, *, task_id: int, decision: str, comment: str) -> dict[str, Any]:
        self.calls.append(
            ("decide_human_task", {"task_id": task_id, "decision": decision, "comment": comment})
        )
        return {
            "id": task_id,
            "status": "approved" if decision == "approve" else "rejected",
            "decision": {"comment": comment},
        }


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


def test_cli_operator_evidence_commands_cover_triage_approval_and_rollback(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)

    triage_exit = run_cli(
        [
            "run",
            "triage",
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
            "--console-url",
            "https://console.example.test",
        ]
    )
    rollback_exit = run_cli(
        [
            "deployment",
            "rollback",
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
            "--expected-current-version-id",
            "44",
            "--rollback-agent-version-id",
            "21",
            "--rollback-reason",
            "candidate regression",
        ]
    )
    approval_exit = run_cli(
        [
            "human-task",
            "decide",
            "--base-url",
            "https://api.example.test",
            "--api-key",
            "test-key",
            "--tenant-id",
            "1",
            "--project-id",
            "2",
            "--task-id",
            "101",
            "--decision",
            "approve",
            "--comment",
            "approved from triage",
        ]
    )

    captured = capsys.readouterr()
    assert triage_exit == 0
    assert rollback_exit == 0
    assert approval_exit == 0
    assert "https://console.example.test/runs/31/triage" in captured.out
    assert "https://console.example.test/replay/compare?source_run_id=31" in captured.out
    assert "https://console.example.test/runs/31#integration-evidence" in captured.out
    assert '"provider": "litellm"' in captured.out
    assert '"provider": "opentelemetry"' in captured.out
    assert "https://console.example.test/deployments/33?tab=promotion" in captured.out
    assert '"agent_version_id": 21' in captured.out
    assert '"status": "approved"' in captured.out


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


def test_productized_publish_uses_manifest_and_prints_next_action(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    FakeNativeAPIClient.seed_agents = []
    FakeNativeAPIClient.seed_versions = {}
    FakeNativeAPIClient.seed_deployments = []
    agent_dir = tmp_path / "support-agent"
    agent_dir.mkdir()
    (agent_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": "support-agent",
                "version": "0.1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:build_graph",
                },
                "capabilities": {"invoke": True},
            }
        ),
        encoding="utf-8",
    )

    exit_code = run_cli(["publish", str(agent_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"agent_name": "support-agent"' in captured.out
    assert "next command: dimoorun deploy support-agent --env local" in captured.out
    assert FakeNativeAPIClient.last_instance is not None
    calls = [call[0] for call in FakeNativeAPIClient.last_instance.calls]
    assert calls[:4] == [
        "validate_package",
        "list_agents",
        "create_agent",
        "list_agent_versions",
    ]


def test_productized_deploy_resolves_agent_and_ready_version(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    FakeNativeAPIClient.seed_agents = [{"id": 11, "name": "support-agent", "status": "active"}]
    FakeNativeAPIClient.seed_versions = {
        11: [{"id": 21, "agent_id": 11, "version": "0.1.0", "status": "ready"}]
    }
    FakeNativeAPIClient.seed_deployments = []

    exit_code = run_cli(["deploy", "support-agent", "--env", "local"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"deployment_id": 24' in captured.out
    assert "next command: dimoorun run support-agent --env local" in captured.out
    assert FakeNativeAPIClient.last_instance is not None
    assert ("list_deployments", {}) in FakeNativeAPIClient.last_instance.calls


def test_productized_run_resolves_deployment_and_can_watch(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    monkeypatch.setattr(cli_main, "sleep", lambda _seconds: None)
    FakeNativeAPIClient.seed_agents = [{"id": 11, "name": "support-agent", "status": "active"}]
    FakeNativeAPIClient.seed_versions = {}
    FakeNativeAPIClient.seed_deployments = [
        {
            "id": 24,
            "agent_id": 11,
            "agent_version_id": 21,
            "environment": "local",
            "desired_status": "active",
        }
    ]

    exit_code = run_cli(
        [
            "run",
            "support-agent",
            "--env",
            "local",
            "--input-json",
            '{"message":"hello"}',
            "--watch",
            "--max-polls",
            "2",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"run_id": 31' in captured.out
    assert "http://127.0.0.1:8080/runs/31" in captured.out
    assert '"status": "succeeded"' in captured.out


def test_productized_open_prints_console_deep_link(capsys: Any) -> None:
    exit_code = run_cli(["open", "--run-id", "31"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "http://127.0.0.1:8080/runs/31"


def test_productized_cli_first_run_path_uses_real_native_api(
    cli_native_api: tuple[str, TestClient, Session],
    tmp_path: Path,
    capsys: Any,
) -> None:
    api_key, test_client, _session = cli_native_api
    base_args = [
        "--base-url",
        "https://api.example.test",
        "--api-key",
        api_key,
    ]
    agent_dir = tmp_path / "support-agent"
    agent_dir.mkdir()
    (agent_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": "support-agent",
                "version": "0.1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:build_graph",
                },
                "capabilities": {"invoke": True},
            }
        ),
        encoding="utf-8",
    )

    assert run_cli(["publish", str(agent_dir), *base_args]) == 0
    publish_output = capsys.readouterr().out
    assert '"agent_name": "support-agent"' in publish_output
    assert "next command: dimoorun deploy support-agent --env local" in publish_output

    assert run_cli(["deploy", "support-agent", "--env", "local", *base_args]) == 0
    deploy_output = capsys.readouterr().out
    deployment_id = int(re.search(r'"deployment_id":\s*(\d+)', deploy_output).group(1))  # type: ignore[union-attr]
    assert "next command: dimoorun run support-agent --env local" in deploy_output

    assert (
        run_cli(
            [
                "run",
                "support-agent",
                "--env",
                "local",
                "--input-json",
                '{"message":"ship first run"}',
                "--thread-id",
                "p0a-real-native-api",
                *base_args,
            ]
        )
        == 0
    )
    run_output = capsys.readouterr().out
    run_id = int(re.search(r'"run_id":\s*(\d+)', run_output).group(1))  # type: ignore[union-attr]
    assert f"http://127.0.0.1:8080/runs/{run_id}" in run_output

    assert run_cli(["open", "--run-id", str(run_id)]) == 0
    assert capsys.readouterr().out.strip() == f"http://127.0.0.1:8080/runs/{run_id}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }
    run_detail = test_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert run_detail.status_code == 200
    assert run_detail.json()["deployment_id"] == deployment_id
    assert run_detail.json()["input"] == {"message": "ship first run"}
    events = test_client.get(f"/v1/runs/{run_id}/events", headers=headers)
    assert events.status_code == 200
    assert any(item["type"] == "run.created" for item in events.json())


def test_demo_seed_prepares_real_native_api_run_evidence(
    cli_native_api: tuple[str, TestClient, Session],
    capsys: Any,
) -> None:
    api_key, test_client, _session = cli_native_api

    assert (
        run_cli(
            [
                "demo",
                "seed",
                "--path",
                "examples/langgraph/support-agent",
                "--base-url",
                "https://api.example.test",
                "--api-key",
                api_key,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    run_id = int(re.search(r'"run_id":\s*(\d+)', output).group(1))  # type: ignore[union-attr]
    deployment_id = int(re.search(r'"deployment_id":\s*(\d+)', output).group(1))  # type: ignore[union-attr]
    assert '"agent_name": "support-agent"' in output
    assert f"http://127.0.0.1:8080/runs/{run_id}" in output
    assert '"dashboard": "http://127.0.0.1:8080/dashboard"' in output

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Tenant-Id": "1",
        "X-Project-Id": "1",
    }
    run_detail = test_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert run_detail.status_code == 200
    assert run_detail.json()["deployment_id"] == deployment_id
    assert run_detail.json()["thread_id"] == "p0a-demo-seed"


def test_demo_seed_combines_publish_deploy_and_run(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    monkeypatch.setattr(cli_main, "NativeAPIClient", FakeNativeAPIClient)
    FakeNativeAPIClient.seed_agents = []
    FakeNativeAPIClient.seed_versions = {}
    FakeNativeAPIClient.seed_deployments = []
    agent_dir = tmp_path / "support-agent"
    agent_dir.mkdir()
    (agent_dir / "manifest.json").write_text(
        json.dumps(
            {
                "name": "support-agent",
                "version": "0.1.0",
                "runtime": {
                    "framework": "langgraph",
                    "adapter": "langgraph",
                    "entrypoint": "agent:build_graph",
                },
                "capabilities": {"invoke": True},
            }
        ),
        encoding="utf-8",
    )

    exit_code = run_cli(["demo", "seed", "--path", str(agent_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"agent_name": "support-agent"' in captured.out
    assert '"deployment_id": 24' in captured.out
    assert '"run_id": 31' in captured.out
    assert '"dashboard": "http://127.0.0.1:8080/dashboard"' in captured.out
