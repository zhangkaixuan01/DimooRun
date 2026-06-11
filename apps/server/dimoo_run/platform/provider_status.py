import os
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from dimoo_run.core.config import Settings
from dimoo_run.domain.models import (
    ModelGateway,
    NotificationChannel,
    ObservabilityExporter,
    Secret,
    WebhookSubscription,
)


def build_provider_status_views(
    session: Session,
    *,
    settings: Settings,
    tenant_id: int,
    project_id: int,
) -> list[dict[str, Any]]:
    secret_count = _count(session, Secret, tenant_id=tenant_id, project_id=project_id)
    gateway_count = _count(session, ModelGateway, tenant_id=tenant_id, project_id=project_id)
    exporter_count = _count(
        session,
        ObservabilityExporter,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    notification_count = _count(
        session,
        NotificationChannel,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    webhook_count = _count(session, WebhookSubscription, tenant_id=tenant_id, project_id=project_id)
    secret_provider = os.getenv("DIMOORUN_SECRET_PROVIDER", "memory")
    return [
        {
            "provider": "postgres",
            "status": "degraded" if settings.database.url.startswith("sqlite") else "healthy",
            "summary": settings.database.url,
            "reason": "SQLite is suitable for local development only."
            if settings.database.url.startswith("sqlite")
            else "External database configured.",
        },
        {
            "provider": "redis",
            "status": "healthy" if _queue_backend(settings) == "redis" else "degraded",
            "summary": settings.redis.url,
            "reason": "Queue backend uses Redis."
            if _queue_backend(settings) == "redis"
            else "Runtime is still using an in-memory queue backend.",
        },
        {
            "provider": "object_store",
            "status": "healthy" if settings.object_store.backend in {"s3", "minio"} else "degraded",
            "summary": f"{settings.object_store.backend}:{settings.object_store.bucket}",
            "reason": "Durable object storage configured."
            if settings.object_store.backend in {"s3", "minio"}
            else "Artifacts are still stored locally.",
        },
        {
            "provider": "secret_provider",
            "status": "healthy" if secret_provider != "memory" and secret_count > 0 else "offline",
            "summary": secret_provider,
            "reason": f"{secret_count} scoped secret reference(s) registered.",
        },
        {
            "provider": "model_gateway",
            "status": "healthy" if gateway_count > 0 else "offline",
            "summary": os.getenv("DIMOORUN_MODEL_GATEWAY_PROVIDER", "builtin"),
            "reason": f"{gateway_count} active model gateway record(s).",
        },
        {
            "provider": "webhook_transport",
            "status": "healthy" if webhook_count > 0 else "degraded",
            "summary": "webhook subscriptions",
            "reason": f"{webhook_count} subscription(s) configured.",
        },
        {
            "provider": "notification_transport",
            "status": "healthy" if notification_count > 0 else "degraded",
            "summary": "notification channels",
            "reason": f"{notification_count} channel(s) configured.",
        },
        {
            "provider": "observability_exporter",
            "status": (
                "healthy"
                if exporter_count > 0 or settings.observability.exporters
                else "offline"
            ),
            "summary": ",".join(settings.observability.exporters) or "none",
            "reason": f"{exporter_count} exporter record(s) configured.",
        },
    ]


def _count(
    session: Session,
    model: type[Any],
    *,
    tenant_id: int,
    project_id: int,
) -> int:
    filters = [model.tenant_id == tenant_id, model.is_deleted.is_(False)]
    if hasattr(model, "project_id"):
        filters.append((model.project_id == project_id) | (model.project_id.is_(None)))
    result = session.scalar(select(func.count(model.id)).where(*filters))
    return int(result or 0)


def _queue_backend(settings: Settings) -> str:
    return os.getenv(
        "DIMOORUN_QUEUE_BACKEND",
        "redis" if settings.runtime.native_runtime_store == "sqlalchemy" else "memory",
    )
