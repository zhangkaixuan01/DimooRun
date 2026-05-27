from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from dimoo_run.core.events import AgentEvent
from dimoo_run.observability.audit import InMemoryComplianceAuditLog
from dimoo_run.observability.policies import RedactionPolicy


class WebhookTransport(Protocol):
    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> None: ...


@dataclass(frozen=True)
class WebhookSubscription:
    id: str
    tenant_id: str
    project_id: str | None
    name: str
    event_types: set[str]
    target_url: str
    secret_ref: str
    permissions: set[str]
    status: str = "active"
    retry_policy: dict[str, Any] = field(default_factory=dict)
    rate_limit_per_minute: int = 60

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "project_id": self.project_id,
            "name": self.name,
            "event_types": sorted(self.event_types),
            "target_url": self.target_url,
            "secret_ref": "[REDACTED]",
            "permissions": sorted(self.permissions),
            "status": self.status,
            "retry_policy": self.retry_policy,
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }


@dataclass(frozen=True)
class WebhookDelivery:
    subscription_id: str
    event_id: str | None
    status: str
    reason: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WebhookSubscriptionService:
    def __init__(
        self,
        *,
        transport: WebhookTransport,
        audit_log: InMemoryComplianceAuditLog,
        redaction_policy: RedactionPolicy | None = None,
    ) -> None:
        self.transport = transport
        self.audit_log = audit_log
        self.redaction_policy = redaction_policy or RedactionPolicy(fields={"secret", "api_key"})
        self.subscriptions: dict[str, WebhookSubscription] = {}
        self.deliveries: list[WebhookDelivery] = []
        self._delivery_windows: dict[str, tuple[datetime, int]] = {}

    def subscribe(
        self,
        *,
        tenant_id: str,
        project_id: str | None,
        name: str,
        event_types: set[str],
        target_url: str,
        secret_ref: str,
        permissions: set[str],
    ) -> WebhookSubscription:
        if "event:receive" not in permissions:
            raise PermissionError("webhook_subscription_permission_required")
        subscription = WebhookSubscription(
            id=str(uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            event_types=event_types,
            target_url=target_url,
            secret_ref=secret_ref,
            permissions=permissions,
        )
        self.subscriptions[subscription.id] = subscription
        return subscription

    def dispatch(self, event: AgentEvent, *, tenant_id: str, project_id: str | None) -> int:
        delivered = 0
        for subscription in self.subscriptions.values():
            if not self._matches(
                subscription,
                event=event,
                tenant_id=tenant_id,
                project_id=project_id,
            ):
                continue
            if not self._allow_rate(subscription):
                self._record_delivery(subscription, event, status="failed", reason="rate_limited")
                continue
            payload = self.redaction_policy.apply(
                {
                    "event_id": event.event_id,
                    "type": event.type,
                    "run_id": event.run_id,
                    "attempt_id": event.attempt_id,
                    "sequence": event.sequence,
                    "payload": event.payload,
                }
            )
            try:
                self.transport.post(
                    subscription.target_url,
                    payload,
                    headers={"X-DimooRun-Webhook-Secret-Ref": subscription.secret_ref},
                )
            except Exception as exc:  # noqa: BLE001
                self._record_delivery(subscription, event, status="failed", reason=str(exc))
                continue
            self._record_delivery(subscription, event, status="delivered")
            delivered += 1
        return delivered

    def _matches(
        self,
        subscription: WebhookSubscription,
        *,
        event: AgentEvent,
        tenant_id: str,
        project_id: str | None,
    ) -> bool:
        return (
            subscription.status == "active"
            and subscription.tenant_id == tenant_id
            and subscription.project_id == project_id
            and event.type in subscription.event_types
        )

    def _allow_rate(self, subscription: WebhookSubscription) -> bool:
        now = datetime.now(UTC)
        window_start, count = self._delivery_windows.get(subscription.id, (now, 0))
        if now - window_start >= timedelta(minutes=1):
            window_start = now
            count = 0
        if count >= subscription.rate_limit_per_minute:
            self._delivery_windows[subscription.id] = (window_start, count)
            return False
        self._delivery_windows[subscription.id] = (window_start, count + 1)
        return True

    def _record_delivery(
        self,
        subscription: WebhookSubscription,
        event: AgentEvent,
        *,
        status: str,
        reason: str | None = None,
    ) -> None:
        self.deliveries.append(
            WebhookDelivery(
                subscription_id=subscription.id,
                event_id=event.event_id,
                status=status,
                reason=reason,
            )
        )
        self.audit_log.record(
            tenant_id=subscription.tenant_id,
            project_id=subscription.project_id,
            actor_id=None,
            actor_type="system",
            action="webhook.dispatch",
            resource_type="webhook_subscription",
            resource_id=subscription.id,
            result="allow" if status == "delivered" else "deny",
            metadata={"event_id": event.event_id, "reason": reason},
        )


@dataclass
class InMemoryWebhookTransport:
    requests: list[dict[str, Any]] = field(default_factory=list)
    fail_next: bool = False

    def post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("webhook_delivery_failed")
        self.requests.append({"url": url, "payload": payload, "headers": headers})
