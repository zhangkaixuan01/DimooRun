from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class CheckpointIndexRecord:
    run_id: str
    thread_id: str
    checkpoint_id: str
    payload_uri: str
    checkpoint_ns: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class CheckpointIndexStore:
    def __init__(self) -> None:
        self._records: list[CheckpointIndexRecord] = []

    def add(
        self,
        *,
        run_id: str,
        thread_id: str,
        checkpoint_id: str,
        payload_uri: str,
        checkpoint_ns: str | None = None,
    ) -> CheckpointIndexRecord:
        record = CheckpointIndexRecord(
            run_id=run_id,
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            payload_uri=payload_uri,
            checkpoint_ns=checkpoint_ns,
        )
        self._records.append(record)
        return record

    def list_by_run(self, run_id: str) -> list[CheckpointIndexRecord]:
        return [record for record in self._records if record.run_id == run_id]
