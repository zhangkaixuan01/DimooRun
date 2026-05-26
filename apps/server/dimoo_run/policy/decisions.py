from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Decision(StrEnum):
    allow = "allow"
    deny = "deny"
    allow_with_redaction = "allow_with_redaction"
    allow_with_limit = "allow_with_limit"
    require_approval = "require_approval"
    require_dry_run = "require_dry_run"
    fallback = "fallback"


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str | None = None
    matched_policy_ids: tuple[str, ...] = ()
    limits: dict[str, Any] = field(default_factory=dict)
    redactions: tuple[str, ...] = ()
    approval_required: bool = False
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(decision=Decision.allow)

    @classmethod
    def deny(cls, *, reason: str, policy_id: str | None = None) -> "PolicyDecision":
        return cls(
            decision=Decision.deny,
            reason=reason,
            matched_policy_ids=tuple(filter(None, [policy_id])),
        )

    @classmethod
    def require_approval(
        cls,
        *,
        reason: str,
        policy_id: str | None = None,
    ) -> "PolicyDecision":
        return cls(
            decision=Decision.require_approval,
            reason=reason,
            matched_policy_ids=tuple(filter(None, [policy_id])),
            approval_required=True,
        )
