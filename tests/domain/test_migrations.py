from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from dimoo_run.domain.models import Tenant
from dimoo_run.persistence.database import Base
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session


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
        "published_surfaces",
        "ingress_routes",
        "runs",
        "tasks",
    ]:
        orm_indexes = {index.name for index in Base.metadata.tables[table_name].indexes}
        database_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        assert orm_indexes <= database_indexes, table_name


def test_alembic_head_matches_task_columns_required_by_orm(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "dimoorun.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    task_columns = {column["name"] for column in inspect(engine).get_columns("tasks")}

    assert "metadata_json" in task_columns


def test_alembic_head_hardens_runtime_operation_columns(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "dimoorun.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    upgrade(config, "head")
    inspector = inspect(create_engine(f"sqlite:///{database_path}"))

    scheduled_columns = {
        column["name"] for column in inspector.get_columns("scheduled_runs")
    }
    assert {
        "schedule_type",
        "timezone",
        "next_fire_at",
        "last_triggered_at",
        "last_run_id",
        "last_task_id",
        "last_run_status",
        "missed_run_policy",
        "backfill_policy",
        "pause_reason",
        "trigger_count",
    } <= scheduled_columns

    batch_columns = {column["name"] for column in inspector.get_columns("batch_runs")}
    assert {
        "deployment_id",
        "total_items",
        "queued_items",
        "running_items",
        "completed_items",
        "failed_items",
        "dead_letter_items",
        "cancelled_items",
        "partial_failure_policy",
        "cancel_policy",
        "last_recomputed_at",
    } <= batch_columns


def test_sqlite_metadata_create_all_autoincrements_mixin_ids() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        tenant = Tenant(name="Default Tenant", slug="default-tenant", status="active")
        session.add(tenant)
        session.flush()

        assert tenant.id == 1
        assert session.scalar(select(Tenant).where(Tenant.slug == "default-tenant")) == tenant
