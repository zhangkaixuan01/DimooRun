from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


class NotificationConfigurationError(RuntimeError):
    error_code = "notification_configuration_invalid"


@dataclass(frozen=True)
class NotificationChannel:
    id: str
    tenant_id: str
    project_id: str
    type: str
    target_ref: str
    status: str = "active"


@dataclass(frozen=True)
class AlertRule:
    id: str
    tenant_id: str
    project_id: str
    name: str
    signal: str
    threshold: float
    channel_id: str
    status: str = "active"


@dataclass(frozen=True)
class IncidentEvent:
    id: str
    tenant_id: str
    project_id: str
    signal: str
    severity: str
    status: str
    source_ref: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)


class NotificationService:
    def __init__(self) -> None:
        self.channels: dict[str, NotificationChannel] = {}
        self.rules: dict[str, AlertRule] = {}
        self.incidents: list[IncidentEvent] = []
        self.deliveries: list[dict[str, Any]] = []

    def register_channel(self, channel: NotificationChannel) -> NotificationChannel:
        self.channels[channel.id] = channel
        return channel

    def register_rule(self, rule: AlertRule) -> AlertRule:
        self._validate_rule_channel(rule)
        self.rules[rule.id] = rule
        return rule

    def evaluate_signal(
        self,
        *,
        tenant_id: str,
        project_id: str,
        signal: str,
        value: float,
        source_ref: str,
    ) -> IncidentEvent | None:
        for rule in self.rules.values():
            if (
                rule.tenant_id == tenant_id
                and rule.project_id == project_id
                and rule.signal == signal
                and rule.status == "active"
                and value >= rule.threshold
            ):
                self._validate_rule_channel(rule)
                incident = IncidentEvent(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    signal=signal,
                    severity="warning",
                    status="open",
                    source_ref=source_ref,
                    value=value,
                    metadata={"rule_id": rule.id},
                )
                self.incidents.append(incident)
                self.deliveries.append({"channel_id": rule.channel_id, "incident_id": incident.id})
                return incident
        return None

    def _validate_rule_channel(self, rule: AlertRule) -> None:
        channel = self.channels.get(rule.channel_id)
        if channel is None:
            raise NotificationConfigurationError("notification_channel_not_found")
        if channel.tenant_id != rule.tenant_id or channel.project_id != rule.project_id:
            raise NotificationConfigurationError("notification_channel_scope_mismatch")
        if channel.status != "active":
            raise NotificationConfigurationError("notification_channel_inactive")
