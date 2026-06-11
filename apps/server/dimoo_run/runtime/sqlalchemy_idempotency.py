import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dimoo_run.domain.models import IdempotencyRecord as IdempotencyRecordModel
from dimoo_run.runtime.idempotency import (
    IdempotencyConflictError,
    IdempotencyReservation,
)


class SQLAlchemyIdempotencyStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def reserve(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyReservation:
        existing = self._find_record(
            tenant_id=tenant_id,
            project_id=project_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return self._reservation_from_existing(existing, request_hash)

        record = IdempotencyRecordModel(
            tenant_id=tenant_id,
            project_id=project_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="pending",
        )
        self.session.add(record)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            existing = self._find_record(
                tenant_id=tenant_id,
                project_id=project_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            return self._reservation_from_existing(existing, request_hash)
        return IdempotencyReservation(record_id=record.id, is_replay=False)

    def complete(self, record_id: int, response: dict[str, Any]) -> None:
        record = self.session.get(IdempotencyRecordModel, record_id)
        if record is None:
            raise KeyError(record_id)
        record.status = "completed"
        record.response_ref = _encode_response(response)
        self.session.flush()

    def _find_record(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        endpoint: str,
        idempotency_key: str,
    ) -> IdempotencyRecordModel | None:
        return self.session.scalar(
            select(IdempotencyRecordModel).where(
                IdempotencyRecordModel.tenant_id == tenant_id,
                IdempotencyRecordModel.project_id == project_id,
                IdempotencyRecordModel.endpoint == endpoint,
                IdempotencyRecordModel.idempotency_key == idempotency_key,
            )
        )

    def _reservation_from_existing(
        self,
        record: IdempotencyRecordModel,
        request_hash: str,
    ) -> IdempotencyReservation:
        if record.request_hash != request_hash:
            raise IdempotencyConflictError(record.idempotency_key)
        return IdempotencyReservation(
            record_id=record.id,
            is_replay=True,
            response=_decode_response(record.response_ref),
        )


def _encode_response(response: dict[str, Any]) -> str:
    return "json:" + json.dumps(response, sort_keys=True, separators=(",", ":"))


def _decode_response(value: str | None) -> dict[str, Any] | None:
    if value is None or not value.startswith("json:"):
        return None
    decoded = json.loads(value.removeprefix("json:"))
    return decoded if isinstance(decoded, dict) else None
