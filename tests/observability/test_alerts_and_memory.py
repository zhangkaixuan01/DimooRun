import pytest
from dimoo_run.memory.providers import SemanticStoreProviderRegistry
from dimoo_run.notifications.alerts import (
    AlertRule,
    NotificationChannel,
    NotificationConfigurationError,
    NotificationService,
)


def test_semantic_store_provider_keeps_boundary_metadata() -> None:
    registry = SemanticStoreProviderRegistry()

    provider = registry.register(
        tenant_id=1,
        project_id=1,
        name="pgvector",
        embedding_model="text-embedding-3-small",
        embedding_gateway_id="gateway_1",
        connection_ref="secret:pgvector",
        retention_policy_id="retention_30d",
        metadata={"dimensions": 1536},
    )

    assert provider.embedding_gateway_id == "gateway_1"
    assert provider.connection_ref == "secret:pgvector"
    assert registry.get(provider.id).metadata["dimensions"] == 1536


def test_alert_rule_creates_incident_without_blocking_runtime() -> None:
    service = NotificationService()
    channel = service.register_channel(
        NotificationChannel(
            id="channel_1",
            tenant_id=1,
            project_id=1,
            type="webhook",
            target_ref="secret:webhook",
        )
    )
    service.register_rule(
        AlertRule(
            id="rule_1",
            tenant_id=1,
            project_id=1,
            name="failure-rate",
            signal="run_failed_rate_high",
            threshold=0.2,
            channel_id=channel.id,
        )
    )

    incident = service.evaluate_signal(
        tenant_id=1,
        project_id=1,
        signal="run_failed_rate_high",
        value=0.5,
        source_ref="metric://run_failed_rate",
    )

    assert incident is not None
    assert incident.status == "open"
    assert incident.source_ref == "metric://run_failed_rate"
    assert incident.value == 0.5
    assert service.deliveries[0]["channel_id"] == "channel_1"


def test_alert_rule_requires_active_channel_in_same_scope() -> None:
    service = NotificationService()
    service.register_channel(
        NotificationChannel(
            id="inactive_channel",
            tenant_id=1,
            project_id=1,
            type="webhook",
            target_ref="secret:webhook",
            status="disabled",
        )
    )
    service.register_channel(
        NotificationChannel(
            id="other_scope_channel",
            tenant_id="tenant_2",
            project_id="project_2",
            type="webhook",
            target_ref="secret:webhook",
        )
    )

    with pytest.raises(NotificationConfigurationError, match="notification_channel_inactive"):
        service.register_rule(
            AlertRule(
                id="rule_inactive",
                tenant_id=1,
                project_id=1,
                name="failure-rate",
                signal="run_failed_rate_high",
                threshold=0.2,
                channel_id="inactive_channel",
            )
        )

    with pytest.raises(NotificationConfigurationError, match="notification_channel_scope_mismatch"):
        service.register_rule(
            AlertRule(
                id="rule_cross_scope",
                tenant_id=1,
                project_id=1,
                name="failure-rate",
                signal="run_failed_rate_high",
                threshold=0.2,
                channel_id="other_scope_channel",
            )
        )
