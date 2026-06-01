from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.observability.policies import RedactionPolicy


class NotificationConfigurationError(RuntimeError):
    error_code = "notification_configuration_invalid"


@dataclass(frozen=True)
class NotificationChannel:
    id: int
    tenant_id: int
    project_id: int | None
    type: str
    target_ref: str
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertRule:
    id: int
    tenant_id: int
    project_id: int | None
    name: str
    signal: str
    threshold: float
    channel_id: int
    status: str = "active"
    dedupe_window_seconds: int = 300
    cooldown_seconds: int = 60


@dataclass(frozen=True)
class IncidentEvent:
    id: int
    tenant_id: int
    project_id: int | None
    signal: str
    severity: str
    status: str
    source_ref: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)
    acknowledged_by: str | None = None
    resolved_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


class NotificationService:
    def __init__(
        self,
        *,
        audit_log: InMemoryComplianceAuditLog | None = None,
        redaction_policy: RedactionPolicy | None = None,
    ) -> None:
        self.channels: dict[int, NotificationChannel] = {}
        self.rules: dict[int, AlertRule] = {}
        self.incidents: list[IncidentEvent] = []
        self.deliveries: list[dict[str, Any]] = []
        self.failed_deliveries: list[dict[str, Any]] = []
        self.audit_log = audit_log
        self.redaction_policy = redaction_policy or RedactionPolicy(fields={"secret", "api_key"})
        self._last_delivery_at: dict[int, datetime] = {}
        self._next_incident_id = 0

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
        tenant_id: int,
        project_id: int | None,
        signal: str,
        value: float,
        source_ref: str,
        payload: dict[str, Any] | None = None,
    ) -> IncidentEvent | None:
        now = datetime.now(UTC)
        for rule in self.rules.values():
            if (
                rule.tenant_id == tenant_id
                and rule.project_id == project_id
                and rule.signal == signal
                and rule.status == "active"
                and value >= rule.threshold
            ):
                self._validate_rule_channel(rule)
                deduped = self._find_open_duplicate(rule=rule, source_ref=source_ref, now=now)
                if deduped is not None:
                    return deduped
                if self._is_in_cooldown(rule, now=now):
                    return None
                incident = IncidentEvent(
                    id=self._allocate_incident_id(),
                    tenant_id=tenant_id,
                    project_id=project_id,
                    signal=signal,
                    severity="warning",
                    status="open",
                    source_ref=source_ref,
                    value=value,
                    metadata={
                        "rule_id": rule.id,
                        "payload": self.redaction_policy.apply(payload or {}),
                    },
                )
                self.incidents.append(incident)
                self._deliver(rule=rule, incident=incident)
                self._last_delivery_at[rule.id] = now
                return incident
        return None

    def acknowledge_incident(self, incident_id: int, *, actor_id: str) -> IncidentEvent:
        incident = self._get_incident(incident_id)
        updated = self._replace_incident(
            incident,
            status="acknowledged",
            acknowledged_by=actor_id,
            updated_at=datetime.now(UTC),
        )
        self._audit_incident_action(updated, action="incident.acknowledge", actor_id=actor_id)
        return updated

    def resolve_incident(self, incident_id: int, *, actor_id: str) -> IncidentEvent:
        incident = self._get_incident(incident_id)
        updated = self._replace_incident(
            incident,
            status="resolved",
            resolved_by=actor_id,
            updated_at=datetime.now(UTC),
        )
        self._audit_incident_action(updated, action="incident.resolve", actor_id=actor_id)
        return updated

    def _validate_rule_channel(self, rule: AlertRule) -> None:
        channel = self.channels.get(rule.channel_id)
        if channel is None:
            raise NotificationConfigurationError("notification_channel_not_found")
        if channel.tenant_id != rule.tenant_id or channel.project_id != rule.project_id:
            raise NotificationConfigurationError("notification_channel_scope_mismatch")
        if channel.status != "active":
            raise NotificationConfigurationError("notification_channel_inactive")

    def _find_open_duplicate(
        self,
        *,
        rule: AlertRule,
        source_ref: str,
        now: datetime,
    ) -> IncidentEvent | None:
        window_start = now - timedelta(seconds=rule.dedupe_window_seconds)
        for incident in reversed(self.incidents):
            if (
                incident.tenant_id == rule.tenant_id
                and incident.project_id == rule.project_id
                and incident.signal == rule.signal
                and incident.source_ref == source_ref
                and incident.status in {"open", "acknowledged"}
                and incident.created_at >= window_start
            ):
                return incident
        return None

    def _is_in_cooldown(self, rule: AlertRule, *, now: datetime) -> bool:
        last_delivery_at = self._last_delivery_at.get(rule.id)
        return (
            last_delivery_at is not None
            and now - last_delivery_at < timedelta(seconds=rule.cooldown_seconds)
        )

    def _deliver(self, *, rule: AlertRule, incident: IncidentEvent) -> None:
        channel = self.channels[rule.channel_id]
        payload = self.redaction_policy.apply(
            {
                "channel_id": rule.channel_id,
                "incident_id": incident.id,
                "signal": incident.signal,
                "value": incident.value,
                "metadata": incident.metadata,
            }
        )
        try:
            if channel.metadata.get("fail_delivery"):
                raise RuntimeError("notification_delivery_failed")
            self.deliveries.append(payload)
        except Exception as exc:  # noqa: BLE001
            self.failed_deliveries.append({**payload, "reason": str(exc)})

    def _get_incident(self, incident_id: int) -> IncidentEvent:
        for incident in self.incidents:
            if incident.id == incident_id:
                return incident
        raise KeyError(incident_id)

    def _replace_incident(self, incident: IncidentEvent, **changes: Any) -> IncidentEvent:
        updated = IncidentEvent(
            id=incident.id,
            tenant_id=incident.tenant_id,
            project_id=incident.project_id,
            signal=incident.signal,
            severity=incident.severity,
            status=changes.get("status", incident.status),
            source_ref=incident.source_ref,
            value=incident.value,
            metadata=incident.metadata,
            acknowledged_by=changes.get("acknowledged_by", incident.acknowledged_by),
            resolved_by=changes.get("resolved_by", incident.resolved_by),
            created_at=incident.created_at,
            updated_at=changes.get("updated_at", incident.updated_at),
        )
        self.incidents[self.incidents.index(incident)] = updated
        return updated

    def _audit_incident_action(
        self,
        incident: IncidentEvent,
        *,
        action: str,
        actor_id: str,
    ) -> None:
        if self.audit_log is None:
            return
        self.audit_log.record(
            tenant_id=incident.tenant_id,
            project_id=incident.project_id,
            actor_id=actor_id,
            actor_type="user",
            action=action,
            resource_type="incident_event",
            resource_id=incident.id,
            result="allow",
            metadata={"signal": incident.signal, "status": incident.status},
        )

    def _allocate_incident_id(self) -> int:
        self._next_incident_id += 1
        return self._next_incident_id
