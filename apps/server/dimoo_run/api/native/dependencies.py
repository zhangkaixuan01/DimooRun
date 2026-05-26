from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    SQLAlchemyNativeRuntimeStore,
    default_native_runtime,
)
from dimoo_run.core.config import Settings
from dimoo_run.persistence.database import create_session_factory
from dimoo_run.runtime.idempotency import IdempotencyStore

_idempotency_store = IdempotencyStore()


@lru_cache(maxsize=4)
def _session_factory(database_url: str) -> sessionmaker[Session]:
    return create_session_factory(database_url)


def get_native_runtime() -> Generator[
    NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    None,
    None,
]:
    settings = Settings.from_env()
    if settings.runtime.native_runtime_store != "sqlalchemy":
        yield default_native_runtime()
        return

    session_factory = _session_factory(settings.database.url)
    session = session_factory()
    try:
        runtime = SQLAlchemyNativeRuntimeStore(
            session,
            idempotency_store=_idempotency_store,
        )
        yield runtime
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
