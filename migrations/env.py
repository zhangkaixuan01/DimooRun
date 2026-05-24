import sys
from logging.config import fileConfig
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "server"))

from alembic import context  # noqa: E402
from dimoo_run.domain import models  # noqa: E402,F401
from dimoo_run.persistence.database import Base  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite:///"):
        database_path = Path(url.removeprefix("sqlite:///"))
        if database_path.parent != Path("."):
            database_path.parent.mkdir(parents=True, exist_ok=True)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
