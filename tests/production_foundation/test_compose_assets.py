from pathlib import Path

import yaml


def test_compose_declares_production_foundation_services() -> None:
    compose_path = Path("docker-compose.yml")
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert {"server", "worker", "console", "postgres", "redis", "minio"} <= set(
        compose["services"]
    )
    assert compose["services"]["server"]["env_file"] == ".env"
    assert compose["services"]["worker"]["env_file"] == ".env"
    assert compose["services"]["console"]["env_file"] == ".env"
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
