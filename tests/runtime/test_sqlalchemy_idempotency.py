from datetime import datetime
from pathlib import Path

import pytest
from dimoo_run.domain.models import IdempotencyRecord, Project, Tenant
from dimoo_run.persistence.database import Base
from dimoo_run.runtime.idempotency import IdempotencyConflictError
from dimoo_run.runtime.sqlalchemy_idempotency import SQLAlchemyIdempotencyStore
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _seed_scope(session: Session) -> None:
    session.add(Tenant(id=1, name="Default Tenant", slug="default-tenant", status="active"))
    session.flush()
    session.add(
        Project(
            id=1,
            tenant_id=1,
            name="Default Project",
            slug="default-project",
            status="active",
        )
    )
    session.commit()


def test_sqlalchemy_idempotency_replays_completed_response_after_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'idempotency.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_scope(session)
        store = SQLAlchemyIdempotencyStore(session)
        reservation = store.reserve(
            tenant_id=1,
            project_id=1,
            endpoint="/v1/agents/1/tasks",
            idempotency_key="idem_1",
            request_hash="hash_1",
        )
        store.complete(reservation.record_id, {"run_id": 10, "task_id": 20})
        session.commit()

    with Session(engine) as session:
        store = SQLAlchemyIdempotencyStore(session)
        replay = store.reserve(
            tenant_id=1,
            project_id=1,
            endpoint="/v1/agents/1/tasks",
            idempotency_key="idem_1",
            request_hash="hash_1",
        )

    assert replay.is_replay is True
    assert replay.response == {"run_id": 10, "task_id": 20}


def test_sqlalchemy_idempotency_rejects_same_key_with_different_payload(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'idempotency-conflict.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_scope(session)
        store = SQLAlchemyIdempotencyStore(session)
        store.reserve(
            tenant_id=1,
            project_id=1,
            endpoint="/v1/deployments/3/tasks",
            idempotency_key="idem_conflict",
            request_hash="hash_1",
        )
        session.commit()

    with Session(engine) as session:
        store = SQLAlchemyIdempotencyStore(session)
        with pytest.raises(IdempotencyConflictError) as exc_info:
            store.reserve(
                tenant_id=1,
                project_id=1,
                endpoint="/v1/deployments/3/tasks",
                idempotency_key="idem_conflict",
                request_hash="hash_2",
            )

    assert exc_info.value.error_code == "idempotency_key_conflict"


def test_sqlalchemy_idempotency_persists_completed_record_metadata(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'idempotency-record.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_scope(session)
        store = SQLAlchemyIdempotencyStore(session)
        reservation = store.reserve(
            tenant_id=1,
            project_id=1,
            endpoint="/v1/agents/1/tasks",
            idempotency_key="idem_metadata",
            request_hash="hash_meta",
        )
        store.complete(reservation.record_id, {"run_id": 11, "task_id": 21})
        session.commit()
        record = session.get(IdempotencyRecord, reservation.record_id)

    assert record is not None
    assert record.status == "completed"
    assert record.response_ref == 'json:{"run_id":11,"task_id":21}'
    assert isinstance(record.created_at, datetime)
    assert record.created_at is not None
