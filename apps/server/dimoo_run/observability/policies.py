from dataclasses import dataclass
from typing import Any


def _redact_value(value: Any, fields: set[str], replacement: str) -> Any:
    if isinstance(value, dict):
        return {
            key: replacement if key in fields else _redact_value(nested, fields, replacement)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, fields, replacement) for item in value]
    return value


@dataclass(frozen=True)
class RedactionPolicy:
    fields: set[str]
    replacement: str = "[REDACTED]"

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        redacted = _redact_value(payload, self.fields, self.replacement)
        if not isinstance(redacted, dict):
            raise TypeError("redaction_policy_payload_must_be_dict")
        return redacted


@dataclass(frozen=True)
class VisibilityPolicy:
    allowed_levels: set[str]

    def allows(self, visibility_level: str) -> bool:
        return visibility_level in self.allowed_levels


@dataclass(frozen=True)
class SamplingPolicy:
    sample_rate: float = 1.0

    def should_sample(self, trace_id: str) -> bool:
        if self.sample_rate <= 0:
            return False
        if self.sample_rate >= 1:
            return True
        bucket = int.from_bytes(trace_id.encode("utf-8"), "little") % 10_000
        return bucket < int(self.sample_rate * 10_000)
