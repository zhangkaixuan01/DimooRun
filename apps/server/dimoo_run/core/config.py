import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfig(BaseModel):
    mode: Literal["dev", "production", "enterprise"] = "dev"
    environment: str = "local"
    native_runtime_store: Literal["memory", "sqlalchemy"] = "memory"


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/dimoorun.db"


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"


class ConsoleConfig(BaseModel):
    enabled: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )


class ObjectStoreConfig(BaseModel):
    backend: Literal["memory", "local", "s3", "minio"] = "local"
    endpoint_url: str = "http://localhost:9000"
    bucket: str = "dimoorun-artifacts"
    access_key: str = "dimoorun"
    secret_key: str = "dimoorun-dev-secret"
    local_root: str = "./data/artifacts"


class ObservabilityConfig(BaseModel):
    tracing: bool = False
    exporters: list[str] = Field(default_factory=list)


class SandboxConfig(BaseModel):
    mode: Literal["process", "container", "disabled"] = "process"
    cpu_limit: str = "1000m"
    memory_limit: str = "1Gi"


class PackageConfig(BaseModel):
    cache_root: str = "./data/package-cache"
    oci_roots: list[str] = Field(default_factory=lambda: ["./data/packages/oci"])


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    object_store: ObjectStoreConfig = Field(default_factory=ObjectStoreConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    packages: PackageConfig = Field(default_factory=PackageConfig)

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv_defaults()
        runtime_mode = os.getenv("DIMOORUN_RUNTIME_MODE", "dev")
        return cls(
            runtime=RuntimeConfig(
                mode=runtime_mode,  # type: ignore[arg-type]
                environment=os.getenv("DIMOORUN_ENVIRONMENT", "local"),
                native_runtime_store=os.getenv(
                    "DIMOORUN_NATIVE_RUNTIME_STORE",
                    "memory",
                ),  # type: ignore[arg-type]
            ),
            database=DatabaseConfig(
                url=os.getenv("DATABASE_URL", DatabaseConfig().url),
            ),
            redis=RedisConfig(
                url=os.getenv("REDIS_URL", RedisConfig().url),
            ),
            console=ConsoleConfig(
                enabled=os.getenv("DIMOORUN_CONSOLE_ENABLED", "true").lower() != "false",
                cors_origins=_console_cors_origins(runtime_mode),
            ),
            object_store=ObjectStoreConfig(
                backend=os.getenv("OBJECT_STORE_BACKEND", ObjectStoreConfig().backend),  # type: ignore[arg-type]
                endpoint_url=os.getenv(
                    "OBJECT_STORE_ENDPOINT_URL",
                    ObjectStoreConfig().endpoint_url,
                ),
                bucket=os.getenv("OBJECT_STORE_BUCKET", ObjectStoreConfig().bucket),
                access_key=os.getenv("OBJECT_STORE_ACCESS_KEY", ObjectStoreConfig().access_key),
                secret_key=os.getenv("OBJECT_STORE_SECRET_KEY", ObjectStoreConfig().secret_key),
                local_root=os.getenv("OBJECT_STORE_LOCAL_ROOT", ObjectStoreConfig().local_root),
            ),
            observability=ObservabilityConfig(
                tracing=os.getenv("DIMOORUN_TRACING_ENABLED", "false").lower() == "true",
                exporters=_split_csv(os.getenv("DIMOORUN_OBSERVABILITY_EXPORTERS", "")),
            ),
            sandbox=SandboxConfig(
                mode=os.getenv("DIMOORUN_SANDBOX_MODE", SandboxConfig().mode),  # type: ignore[arg-type]
                cpu_limit=os.getenv("DIMOORUN_SANDBOX_CPU_LIMIT", SandboxConfig().cpu_limit),
                memory_limit=os.getenv(
                    "DIMOORUN_SANDBOX_MEMORY_LIMIT",
                    SandboxConfig().memory_limit,
                ),
            ),
            packages=PackageConfig(
                cache_root=os.getenv(
                    "DIMOORUN_PACKAGE_CACHE_ROOT",
                    PackageConfig().cache_root,
                ),
                oci_roots=_split_csv(
                    os.getenv(
                        "DIMOORUN_OCI_PACKAGE_ROOTS",
                        ",".join(PackageConfig().oci_roots),
                    )
                )
                or list(PackageConfig().oci_roots),
            ),
        )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _console_cors_origins(runtime_mode: str) -> list[str]:
    configured = _split_csv(
        os.getenv("DIMOORUN_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    )
    if runtime_mode == "dev":
        for origin in ["http://127.0.0.1:5173", "http://localhost:5173"]:
            if origin not in configured:
                configured.append(origin)
    return configured


def _load_dotenv_defaults() -> None:
    env_path = _find_dotenv()
    if env_path is None:
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _find_dotenv() -> Path | None:
    current = Path.cwd().resolve()
    for path in [current, *current.parents]:
        candidate = path / ".env"
        if candidate.exists():
            return candidate
    return None
