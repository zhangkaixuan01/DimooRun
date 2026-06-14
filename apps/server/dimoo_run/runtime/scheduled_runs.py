from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ScheduleType = Literal["cron", "interval"]
BackfillPolicy = Literal["none", "latest", "all"]
MissedRunPolicy = Literal["skip", "run_once", "catch_up"]


@dataclass(frozen=True)
class SchedulePreview:
    schedule_type: ScheduleType
    timezone: str
    cron_expression: str | None
    interval_minutes: int | None
    next_fire_time: str


def validate_schedule_payload(
    payload: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], SchedulePreview]:
    current = now or datetime.now(UTC)
    timezone = str(payload.get("timezone") or "UTC").strip() or "UTC"
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("invalid_timezone") from exc

    cron_expression = _optional_string(payload.get("cron_expression"))
    interval_minutes = _optional_int(payload.get("interval_minutes"))
    if bool(cron_expression) == bool(interval_minutes):
        raise ValueError("schedule_shape_required")
    if interval_minutes is not None and interval_minutes <= 0:
        raise ValueError("interval_minutes_invalid")
    if cron_expression is not None and not _valid_cron_expression(cron_expression):
        raise ValueError("cron_expression_invalid")

    backfill_policy = str(payload.get("backfill_policy") or "none")
    if backfill_policy not in {"none", "latest", "all"}:
        raise ValueError("backfill_policy_invalid")
    missed_run_policy = str(payload.get("missed_run_policy") or "skip")
    if missed_run_policy not in {"skip", "run_once", "catch_up"}:
        raise ValueError("missed_run_policy_invalid")

    localized_now = current.astimezone(zone)
    if interval_minutes is not None:
        next_fire = localized_now + timedelta(minutes=interval_minutes)
        schedule_type: ScheduleType = "interval"
    else:
        next_fire = _next_cron_fire(localized_now)
        schedule_type = "cron"

    normalized = {
        "name": _optional_string(payload.get("name")) or "runtime-schedule",
        "schedule_type": schedule_type,
        "timezone": timezone,
        "cron_expression": cron_expression,
        "interval_minutes": interval_minutes,
        "deployment_id": int(payload.get("deployment_id") or 0),
        "input_template": dict(payload.get("input_template") or {}),
        "backfill_policy": backfill_policy,
        "missed_run_policy": missed_run_policy,
        "audit_reason": _optional_string(payload.get("audit_reason")),
        "next_fire_time": next_fire.astimezone(UTC).isoformat(),
    }
    next_fire_time = str(normalized["next_fire_time"])
    preview = SchedulePreview(
        schedule_type=schedule_type,
        timezone=timezone,
        cron_expression=cron_expression,
        interval_minutes=interval_minutes,
        next_fire_time=next_fire_time,
    )
    return normalized, preview


def compute_next_fire_time(metadata: dict[str, Any], *, now: datetime | None = None) -> str:
    normalized, preview = validate_schedule_payload(metadata, now=now)
    _ = normalized
    return preview.next_fire_time


def resolve_due_fire_times(
    metadata: dict[str, Any],
    *,
    status: str = "active",
    now: datetime | None = None,
    max_catch_up_runs: int = 25,
) -> tuple[list[str], str]:
    current = now or datetime.now(UTC)
    next_fire = _parse_datetime(metadata.get("next_fire_time"))
    if next_fire is None:
        next_fire = _parse_datetime(compute_next_fire_time(metadata, now=current))
    if next_fire is None or status != "active":
        return [], compute_next_fire_time(metadata, now=current)
    if next_fire > current:
        return [], next_fire.astimezone(UTC).isoformat()

    missed_run_policy = str(metadata.get("missed_run_policy") or "skip")
    if missed_run_policy == "skip":
        while next_fire <= current:
            next_fire = _advance_fire_time(metadata, next_fire)
        return [], next_fire.astimezone(UTC).isoformat()

    due_fire_times: list[str] = []
    if missed_run_policy == "run_once":
        due_fire_times.append(next_fire.astimezone(UTC).isoformat())
        while next_fire <= current:
            next_fire = _advance_fire_time(metadata, next_fire)
        return due_fire_times, next_fire.astimezone(UTC).isoformat()

    while next_fire <= current and len(due_fire_times) < max_catch_up_runs:
        due_fire_times.append(next_fire.astimezone(UTC).isoformat())
        next_fire = _advance_fire_time(metadata, next_fire)
    while next_fire <= current:
        next_fire = _advance_fire_time(metadata, next_fire)
    return due_fire_times, next_fire.astimezone(UTC).isoformat()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("interval_minutes_invalid") from exc


def _valid_cron_expression(value: str) -> bool:
    parts = value.split()
    if len(parts) != 5:
        return False
    allowed = set("0123456789*/,-")
    return all(part and set(part) <= allowed for part in parts)


def _next_cron_fire(current: datetime) -> datetime:
    next_fire = current.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return next_fire


def _advance_fire_time(metadata: dict[str, Any], current_fire: datetime) -> datetime:
    timezone = str(metadata.get("timezone") or "UTC").strip() or "UTC"
    zone = ZoneInfo(timezone)
    localized_current = current_fire.astimezone(zone)
    interval_minutes = _optional_int(metadata.get("interval_minutes"))
    if interval_minutes is not None:
        return (localized_current + timedelta(minutes=interval_minutes)).astimezone(UTC)
    return _next_cron_fire(localized_current).astimezone(UTC)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
