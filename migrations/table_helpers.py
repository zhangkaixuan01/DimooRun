from collections.abc import Iterable
from typing import Any

from alembic import op
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, text


def audit_columns() -> list[Column[Any]]:
    return [
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("created_by", String(64)),
        Column("updated_at", DateTime(timezone=True)),
        Column("updated_by", String(64)),
        Column("is_deleted", Boolean, nullable=False, server_default="0"),
        Column("deleted_at", DateTime(timezone=True)),
        Column("deleted_by", String(64)),
    ]


def id_column() -> Column[str]:
    return Column("id", String(64), primary_key=True)


def tenant_project_columns(project_nullable: bool = True) -> list[Column[Any]]:
    return [
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=project_nullable),
    ]


def metadata_columns(project_nullable: bool = True) -> list[Column[Any]]:
    return [
        id_column(),
        *tenant_project_columns(project_nullable=project_nullable),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    ]


def create_placeholder_table(table_name: str) -> None:
    op.create_table(table_name, *metadata_columns(project_nullable=True))


def drop_tables(table_names: Iterable[str]) -> None:
    for table_name in reversed(tuple(table_names)):
        op.drop_table(table_name)


def create_runtime_stub_table(table_name: str) -> None:
    op.create_table(
        table_name,
        id_column(),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )


def create_named_stub_table(table_name: str) -> None:
    op.create_table(
        table_name,
        id_column(),
        *tenant_project_columns(project_nullable=True),
        Column("name", String(255), nullable=False),
        Column("status", String(64), nullable=False, server_default="active"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )


def create_task_stub_table(table_name: str) -> None:
    op.create_table(
        table_name,
        id_column(),
        Column("run_id", String(64), ForeignKey("runs.id")),
        Column("tenant_id", String(64), ForeignKey("tenants.id"), nullable=False),
        Column("project_id", String(64), ForeignKey("projects.id"), nullable=False),
        Column("status", String(64), nullable=False, server_default="queued"),
        Column("metadata_json", JSON, nullable=False, server_default=text("'{}'")),
        *audit_columns(),
    )


def integer_column(name: str, default: str) -> Column[int]:
    return Column(name, Integer, nullable=False, server_default=default)
