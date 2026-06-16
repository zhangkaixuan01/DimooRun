import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.compose_runtime_smoke import run_compose_runtime_smoke
from scripts.compose_smoke import validate_compose_smoke


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.urls: list[str] = []
        self.requests: list[tuple[str, dict[str, object]]] = []

    def run(self, command: list[str], timeout_seconds: int) -> None:
        self.commands.append(command)

    def probe_url(self, url: str, timeout_seconds: int) -> None:
        self.urls.append(url)

    def request_json(
        self,
        url: str,
        *,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout_seconds: int,
    ) -> dict[str, object]:
        _ = headers, timeout_seconds
        self.requests.append((url, payload))
        if url.endswith("/v1/packages/validate"):
            return {"validation_token": "validation-token-1"}
        if url.endswith("/v1/agents"):
            return {"id": 101}
        if url.endswith("/v1/agents/101/versions"):
            return {"id": 202, "status": "ready"}
        if url.endswith("/v1/deployments"):
            return {"id": 303, "desired_status": "active"}
        if url.endswith("/v1/deployments/303/tasks"):
            return {"run_id": 404, "task_id": 505, "status": "queued"}
        return {"status": "ready"}

    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> object:
        _ = headers, timeout_seconds
        if url.endswith("/v1/runs/404"):
            return {"id": 404, "status": "succeeded", "task_id": 505}
        if url.endswith("/v1/runs/404/events"):
            return [{"type": "attempt.started"}, {"type": "run.succeeded"}]
        if url.endswith("/v1/runs/404/attempts"):
            return [{"id": 606, "status": "succeeded", "attempt_no": 1}]
        raise AssertionError(f"unexpected GET {url}")


def test_compose_declares_production_foundation_services() -> None:
    compose_path = Path("docker-compose.yml")
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert {"migrator", "server", "worker", "console", "postgres", "redis", "minio"} <= set(
        compose["services"]
    )
    assert compose["services"]["migrator"]["command"] == ["python", "-m", "dimoo_run.ops.init_db"]
    assert compose["services"]["server"]["env_file"] == ".env"
    assert compose["services"]["worker"]["env_file"] == ".env"
    assert compose["services"]["console"]["env_file"] == ".env"
    assert compose["services"]["server"]["environment"]["DIMOORUN_SKIP_DB_INIT"] == "true"
    assert compose["services"]["worker"]["environment"]["DIMOORUN_SKIP_DB_INIT"] == "true"
    assert compose["services"]["server"]["environment"]["DATABASE_URL"].startswith(
        "postgresql+psycopg://"
    )
    assert compose["services"]["server"]["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert (
        compose["services"]["server"]["environment"]["OBJECT_STORE_ENDPOINT_URL"]
        == "http://minio:9000"
    )
    assert compose["services"]["postgres"]["image"] == "postgres:16-alpine"
    assert compose["services"]["redis"]["image"] == "redis:8-alpine"
    assert (
        compose["services"]["minio"]["image"]
        == "minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1"
    )


def test_env_example_covers_runtime_dependencies() -> None:
    env = Path(".env.example").read_text(encoding="utf-8")

    for key in [
        "DATABASE_URL=",
        "REDIS_URL=",
        "OBJECT_STORE_ENDPOINT_URL=",
        "VITE_DIMOORUN_API_BASE_URL=",
        "DIMOORUN_CORS_ORIGINS=",
    ]:
        assert key in env


def test_dockerfiles_exist_for_runtime_services() -> None:
    for path in [
        "deploy/docker/server.Dockerfile",
        "deploy/docker/worker.Dockerfile",
        "deploy/docker/console.Dockerfile",
    ]:
        assert Path(path).exists()


def test_server_image_runs_database_initialization_before_api() -> None:
    dockerfile = Path("deploy/docker/server.Dockerfile").read_text(encoding="utf-8")

    assert "alembic.ini" in dockerfile
    assert 'CMD ["python", "-m", "dimoo_run.ops.docker_entrypoint"]' in dockerfile

    entrypoint = Path("apps/server/dimoo_run/ops/docker_entrypoint.py").read_text(
        encoding="utf-8"
    )
    init_db = Path("apps/server/dimoo_run/ops/init_db.py").read_text(encoding="utf-8")
    assert "init_db()" in entrypoint
    assert 'command.upgrade(config, "head")' in init_db
    assert "_seed_default_scope()" in init_db
    assert "ensure_bootstrap_operator()" in init_db


def test_console_image_builds_dist_and_serves_static_bundle() -> None:
    dockerfile = Path("deploy/docker/console.Dockerfile").read_text(encoding="utf-8")

    assert "RUN npm run build" in dockerfile
    assert (
        'CMD ["node", "scripts/serve-dist.mjs", "--host", "0.0.0.0", "--port", "5173"]'
        in dockerfile
    )


def test_dev_compose_mounts_source_and_enables_reload() -> None:
    compose_path = Path("docker-compose.dev.yml")
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    server = compose["services"]["server"]
    console = compose["services"]["console"]

    assert "./apps/server:/app/apps/server" in server["volumes"]
    assert "./migrations:/app/migrations" in server["volumes"]
    assert "--reload" in server["command"][-1]
    assert "--reload-dir /app/apps/server" in server["command"][-1]
    assert "./apps/console:/app/apps/console" in console["volumes"]
    assert "console-node-modules:/app/apps/console/node_modules" in console["volumes"]


def test_compose_console_uses_http_healthcheck() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    console = compose["services"]["console"]
    assert console["healthcheck"]["test"] == [
        "CMD",
        "node",
        "-e",
        "fetch('http://127.0.0.1:5173/').then((response)=>{if(!response.ok)process.exit(1)}).catch(()=>process.exit(1))",
    ]
    assert console["healthcheck"]["interval"] == "10s"
    assert console["healthcheck"]["timeout"] == "5s"
    assert console["healthcheck"]["retries"] == 5


def test_compose_smoke_contract_covers_core_runtime_stack() -> None:
    result = validate_compose_smoke(Path("."))

    assert result.errors == []
    assert result.checked_services == [
        "migrator",
        "server",
        "worker",
        "console",
        "postgres",
        "redis",
        "minio",
    ]


def test_compose_runtime_smoke_runs_config_up_probes_and_down() -> None:
    runner = FakeRunner()

    result = run_compose_runtime_smoke(Path("."), runner=runner, retries=1)

    assert result.errors == []
    assert runner.commands == [
        ["docker", "compose", "config", "--quiet"],
        ["docker", "compose", "up", "--build", "--detach", "--wait"],
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_isready",
            "-U",
            "dimoorun",
            "-d",
            "dimoorun",
        ],
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "minio",
            "sh",
            "-c",
            (
                "mc alias set local http://localhost:9000 "
                "$MINIO_ROOT_USER $MINIO_ROOT_PASSWORD >/dev/null 2>&1 && mc ls local"
            ),
        ],
        ["docker", "compose", "ps"],
        ["docker", "compose", "down", "--remove-orphans", "--volumes"],
    ]
    assert runner.urls == [
        "http://127.0.0.1:8000/healthz",
        "http://127.0.0.1:5173/",
    ]
    assert runner.requests[-2:] == [
        (
            "http://127.0.0.1:8000/v1/backups/dry-run",
            {
                "plan_id": 9,
                "scope": "project",
                "targets": ["runs", "datasets", "audit_logs"],
                "storage_ref": "minio://dimoorun-backups/local",
            },
        ),
        (
            "http://127.0.0.1:8000/v1/backups/restore-dry-run",
            {
                "backup_ref": "backup://2026-06-12/project",
                "restore_scope": "project",
                "targets": ["runs"],
                "destructive": True,
                "confirmation": "RESTORE PROJECT 1",
            },
        ),
    ]


def test_compose_runtime_smoke_creates_and_removes_env_from_example(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("DIMOORUN_DEV_API_KEY=dev-local-key\n", encoding="utf-8")
    runner = FakeRunner()

    result = run_compose_runtime_smoke(tmp_path, runner=runner, retries=1)

    assert result.errors == []
    assert "env-file" in result.checked_steps
    assert not (tmp_path / ".env").exists()
