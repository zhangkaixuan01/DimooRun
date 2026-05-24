from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfig(BaseModel):
    mode: Literal["dev", "production", "enterprise"] = "dev"
    environment: str = "local"


class DatabaseConfig(BaseModel):
    url: str = "sqlite+aiosqlite:///./data/dimoorun.db"


class RedisConfig(BaseModel):
    url: str = "redis://localhost:6379/0"


class ConsoleConfig(BaseModel):
    enabled: bool = True


class ObservabilityConfig(BaseModel):
    tracing: bool = False


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
