from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GoldenCompatibilityRecord:
    operation: str
    expected_semantics: dict[str, Any]
    compat_response: dict[str, Any]
    native_resources: dict[str, Any]
    unsupported_capabilities: list[str] = field(default_factory=list)
    divergence_reason: str | None = None


class GoldenCompatibilityRunner:
    def __init__(self) -> None:
        self.records: list[GoldenCompatibilityRecord] = []

    def record(
        self,
        *,
        operation: str,
        expected_semantics: dict[str, Any] | None,
        compat_response: dict[str, Any] | None,
        native_resources: dict[str, Any] | None,
        unsupported_capabilities: Iterable[str] | None = None,
        divergence_reason: str | None = None,
    ) -> dict[str, Any]:
        unsupported = [str(item) for item in (unsupported_capabilities or [])]
        reason = divergence_reason or (
            "compatibility_not_supported" if unsupported else None
        )
        record = GoldenCompatibilityRecord(
            operation=operation,
            expected_semantics=dict(expected_semantics or {}),
            compat_response=dict(compat_response or {}),
            native_resources=dict(native_resources or {}),
            unsupported_capabilities=unsupported,
            divergence_reason=reason,
        )
        self.records.append(record)
        return asdict(record)

    def latest(self) -> dict[str, Any] | None:
        if not self.records:
            return None
        return asdict(self.records[-1])

    def reset(self) -> None:
        self.records.clear()


_default_golden_runner = GoldenCompatibilityRunner()


def default_golden_runner() -> GoldenCompatibilityRunner:
    return _default_golden_runner


def reset_golden_runner() -> None:
    _default_golden_runner.reset()
