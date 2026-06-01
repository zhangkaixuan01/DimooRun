import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

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
    tenant_slug = os.getenv("DIMOORUN_DEFAULT_TENANT_SLUG", "default-tenant")
    tenant_name = os.getenv("DIMOORUN_DEFAULT_TENANT_NAME", "Default Tenant")
    project_slug = os.getenv("DIMOORUN_DEFAULT_PROJECT_SLUG", "default-project")
    project_name = os.getenv("DIMOORUN_DEFAULT_PROJECT_NAME", "Default Project")
    environment = os.getenv("DIMOORUN_DEFAULT_ENVIRONMENT", "local")
    with session_factory() as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            tenant = Tenant(name=tenant_name, slug=tenant_slug, status="active")
            session.add(tenant)
            session.flush()
        project = session.scalar(
            select(Project).where(Project.tenant_id == tenant.id, Project.slug == project_slug)
        )
        if project is None:
            project = Project(
                tenant_id=tenant.id,
                name=project_name,
                slug=project_slug,
                status="active",
            )
            session.add(project)
            session.flush()
        existing_environment = session.scalar(
            select(Environment).where(
                Environment.tenant_id == tenant.id,
                Environment.project_id == project.id,
                Environment.environment == environment,
            )
        )
        if existing_environment is None:
            session.add(
                Environment(
                    tenant_id=tenant.id,
                    project_id=project.id,
                    name=environment,
                    environment=environment,
                    status="active",
                    metadata_json={"seeded": True},
                )
            )
        session.commit()


if __name__ == "__main__":
    run()
