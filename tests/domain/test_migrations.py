from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from dimoo_run.persistence.database import Base
from sqlalchemy import create_engine, inspect


def test_migration_scripts_are_frozen_contracts() -> None:
    for migration_path in sorted(Path("migrations/versions").glob("*.py")):
        source = migration_path.read_text(encoding="utf-8")
        assert "Base.metadata.create_all" not in source, migration_path
        assert "from dimoo_run.persistence.database import Base" not in source, migration_path


def test_alembic_upgrade_and_downgrade(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "dimoorun.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())

    downgrade(config, "base")
    assert not set(Base.metadata.tables) & set(inspect(engine).get_table_names())


def test_alembic_core_indexes_match_orm_metadata(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "dimoorun.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)

    for table_name in [
        "projects",
        "users",
        "service_accounts",
        "roles",
        "permissions",
        "api_keys",
        "agents",
        "agent_versions",
        "deployments",
        "agent_instances",
        "runs",
        "tasks",
    ]:
        orm_indexes = {index.name for index in Base.metadata.tables[table_name].indexes}
        database_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        assert orm_indexes <= database_indexes, table_name
