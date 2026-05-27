import os
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
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


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


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    object_store: ObjectStoreConfig = Field(default_factory=ObjectStoreConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            runtime=RuntimeConfig(
                mode=os.getenv("DIMOORUN_RUNTIME_MODE", "dev"),  # type: ignore[arg-type]
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
                cors_origins=_split_csv(
                    os.getenv("DIMOORUN_CORS_ORIGINS", "http://localhost:5173")
                ),
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
        )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
