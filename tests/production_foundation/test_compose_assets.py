from pathlib import Path

import yaml


def test_compose_declares_production_foundation_services() -> None:
    compose_path = Path("docker-compose.yml")
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    assert {"server", "worker", "console", "postgres", "redis", "minio"} <= set(
        compose["services"]
    )
    assert compose["services"]["server"]["env_file"] == ".env.example"
    assert compose["services"]["console"]["env_file"] == ".env.example"
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
