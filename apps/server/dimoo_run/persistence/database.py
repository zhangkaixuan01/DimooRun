from collections.abc import Generator
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


class IdMixin:
    id: Mapped[str] = mapped_column(String(64), primary_key=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TenantProjectMixin:
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


def json_column(default: Any | None = None) -> Mapped[dict[str, Any]]:
    return mapped_column(JSON, default=dict if default is None else default, nullable=False)


def text_column(nullable: bool = True) -> Mapped[str | None]:
    return mapped_column(Text, nullable=nullable)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
