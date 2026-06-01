from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    type: str
    payload: dict[str, Any]
    run_id: int | None = None
    attempt_id: int | None = None
    sequence: int | None = None
    event_id: str | None = None
    framework: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    visibility_level: str = "internal"

    def __post_init__(self) -> None:
        if self.event_id is None and self.run_id is not None and self.sequence is not None:
            object.__setattr__(self, "event_id", f"{self.run_id}:{self.sequence}")


@dataclass(frozen=True)
class AgentResult:
    output: dict[str, Any]
    events: list[AgentEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
