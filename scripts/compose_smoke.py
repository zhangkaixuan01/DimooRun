from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_SERVICES = ["migrator", "server", "worker", "console", "postgres", "redis", "minio"]
RUNTIME_ENV = {
    "DATABASE_URL": "postgresql+psycopg://",
    "REDIS_URL": "redis://redis:6379/0",
    "OBJECT_STORE_ENDPOINT_URL": "http://minio:9000",
    "DIMOORUN_NATIVE_RUNTIME_STORE": "sqlalchemy",
}


@dataclass(frozen=True)
class ComposeSmokeResult:
    errors: list[str] = field(default_factory=list)
    checked_services: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_compose_smoke(root: Path) -> ComposeSmokeResult:
    compose_path = root / "docker-compose.yml"
    if not compose_path.exists():
        return ComposeSmokeResult(errors=["docker-compose.yml is missing."])

    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose.get("services", {}) if isinstance(compose, dict) else {}
    errors: list[str] = []

    for service in REQUIRED_SERVICES:
        if service not in services:
            errors.append(f"docker-compose.yml missing service: {service}")

    if errors:
        return ComposeSmokeResult(errors=errors, checked_services=[])

    _validate_core_dependencies(services, errors)
    _validate_migrator(services["migrator"], errors)
    _validate_runtime_service("server", services["server"], errors)
    _validate_runtime_service("worker", services["worker"], errors)
    _validate_console(services["console"], errors)
    _validate_dependency_service("postgres", services["postgres"], "5432:5432", errors)
    _validate_dependency_service("redis", services["redis"], "6379:6379", errors)
    _validate_dependency_service("minio", services["minio"], "9000:9000", errors)

    volumes = compose.get("volumes", {})
    for volume in ["postgres-data", "minio-data"]:
        if volume not in volumes:
            errors.append(f"docker-compose.yml missing durable volume: {volume}")

    return ComposeSmokeResult(errors=errors, checked_services=REQUIRED_SERVICES.copy())


def _validate_core_dependencies(services: dict[str, Any], errors: list[str]) -> None:
    migrator_depends = services["migrator"].get("depends_on", {})
    for dependency in ["postgres", "redis", "minio"]:
        condition = migrator_depends.get(dependency, {}).get("condition")
        if condition != "service_healthy":
            errors.append(f"migrator must wait for healthy {dependency}.")

    server_depends = services["server"].get("depends_on", {})
    if server_depends.get("migrator", {}).get("condition") != "service_completed_successfully":
        errors.append("server must wait for completed migrator job.")
    for dependency in ["postgres", "redis", "minio"]:
        condition = server_depends.get(dependency, {}).get("condition")
        if condition != "service_healthy":
            errors.append(f"server must wait for healthy {dependency}.")

    worker_depends = services["worker"].get("depends_on", {})
    if worker_depends.get("migrator", {}).get("condition") != "service_completed_successfully":
        errors.append("worker must wait for completed migrator job.")
    if worker_depends.get("server", {}).get("condition") != "service_healthy":
        errors.append("worker must wait for healthy server.")

    if (
        services["console"].get("depends_on", {}).get("server", {}).get("condition")
        != "service_healthy"
    ):
        errors.append("console must wait for healthy server.")


def _validate_migrator(service: dict[str, Any], errors: list[str]) -> None:
    if service.get("env_file") != ".env":
        errors.append("migrator must load .env.")
    if service.get("command") != ["python", "-m", "dimoo_run.ops.init_db"]:
        errors.append("migrator must run python -m dimoo_run.ops.init_db.")
    environment = service.get("environment", {})
    if environment.get("DIMOORUN_SKIP_DB_INIT") != "false":
        errors.append("migrator must run with DIMOORUN_SKIP_DB_INIT=false.")


def _validate_runtime_service(name: str, service: dict[str, Any], errors: list[str]) -> None:
    if service.get("env_file") != ".env":
        errors.append(f"{name} must load .env.")

    environment = service.get("environment", {})
    for key, expected in RUNTIME_ENV.items():
        actual = environment.get(key)
        if actual != expected and not str(actual).startswith(expected):
            errors.append(f"{name} environment {key} must point to Compose dependency.")
    if environment.get("DIMOORUN_SKIP_DB_INIT") != "true":
        errors.append(f"{name} must skip inline DB init when migrator is enabled.")

    if name == "server":
        _require_healthcheck(name, service, errors)
        if "8000:8000" not in service.get("ports", []):
            errors.append("server must expose 8000:8000 for local smoke.")


def _validate_console(service: dict[str, Any], errors: list[str]) -> None:
    if service.get("env_file") != ".env":
        errors.append("console must load .env.")
    if "5173:5173" not in service.get("ports", []):
        errors.append("console must expose 5173:5173 for local smoke.")


def _validate_dependency_service(
    name: str,
    service: dict[str, Any],
    required_port: str,
    errors: list[str],
) -> None:
    _require_healthcheck(name, service, errors)
    if required_port not in service.get("ports", []):
        errors.append(f"{name} must expose {required_port} for local smoke.")


def _require_healthcheck(name: str, service: dict[str, Any], errors: list[str]) -> None:
    healthcheck = service.get("healthcheck")
    if not isinstance(healthcheck, dict) or "test" not in healthcheck:
        errors.append(f"{name} must define a healthcheck.")


def main() -> None:
    result = validate_compose_smoke(Path("."))
    if not result.ok:
        for error in result.errors:
            print(f"Compose smoke failed: {error}")
        raise SystemExit(1)
    print(
        "Compose smoke contract passed for services: "
        + ", ".join(result.checked_services)
    )


if __name__ == "__main__":
    main()

