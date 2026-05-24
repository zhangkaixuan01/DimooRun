from alembic.command import downgrade, upgrade
from alembic.config import Config
from dimoo_run.persistence.database import Base
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_and_downgrade(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "dimoorun.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())

    downgrade(config, "base")
    assert not set(Base.metadata.tables) & set(inspect(engine).get_table_names())
