import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from dimoo_run.api.dependencies import ensure_bootstrap_operator
from dimoo_run.core.config import Settings
from dimoo_run.domain.models import Environment, Project, Tenant
from dimoo_run.persistence.database import create_session_factory


def run() -> None:
    config_path = Path(os.getenv("DIMOORUN_ALEMBIC_INI", "alembic.ini"))
    config = Config(str(config_path))
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    _seed_default_scope()
    ensure_bootstrap_operator()


def _seed_default_scope() -> None:
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database.url)
    tenant_id = os.getenv("DIMOORUN_DEFAULT_TENANT_ID", "tenant_1")
    tenant_name = os.getenv("DIMOORUN_DEFAULT_TENANT_NAME", "Default Tenant")
    project_id = os.getenv("DIMOORUN_DEFAULT_PROJECT_ID", "project_1")
    project_name = os.getenv("DIMOORUN_DEFAULT_PROJECT_NAME", "Default Project")
    environment = os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local")
    with session_factory() as session:
        if session.get(Tenant, tenant_id) is None:
            session.add(Tenant(id=tenant_id, name=tenant_name, slug=tenant_id, status="active"))
            session.flush()
        if session.get(Project, project_id) is None:
            session.add(
                Project(
                    id=project_id,
                    tenant_id=tenant_id,
                    name=project_name,
                    slug=project_id,
                    status="active",
                )
            )
            session.flush()
        if session.get(Environment, environment) is None:
            session.add(
                Environment(
                    id=environment,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    name=environment,
                    environment=environment,
                    status="active",
                    metadata_json={"seeded": True},
                )
            )
        session.commit()


if __name__ == "__main__":
    run()
