from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IdempotencyReservation:
    record_id: int
    is_replay: bool
    response: dict[str, Any] | None = None


class IdempotencyConflictError(RuntimeError):
    error_code = "idempotency_key_conflict"


@dataclass
class IdempotencyRecord:
    record_id: int
    request_hash: str
    status: str = "pending"
    response: dict[str, Any] | None = None


class IdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[tuple[int, int | None, str, str], IdempotencyRecord] = {}
        self._next_id = 1

    def reserve(
        self,
        *,
        tenant_id: int,
        project_id: int | None,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyReservation:
        scope = (tenant_id, project_id, endpoint, idempotency_key)
        existing = self._records.get(scope)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError(idempotency_key)
            return IdempotencyReservation(
                record_id=existing.record_id,
                is_replay=True,
                response=existing.response,
            )
        record = IdempotencyRecord(record_id=self._next_id, request_hash=request_hash)
        self._next_id += 1
        self._records[scope] = record
        return IdempotencyReservation(record_id=record.record_id, is_replay=False)

    def complete(self, record_id: int, response: dict[str, Any]) -> None:
        for record in self._records.values():
            if record.record_id == record_id:
                record.status = "completed"
                record.response = response
                return
        raise KeyError(record_id)
