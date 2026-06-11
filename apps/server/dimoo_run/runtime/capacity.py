from __future__ import annotations

import builtins
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from typing import Any, cast

from dimoo_run.api.native.runtime import (
    NativeRuntimeStore,
    NativeTask,
    SQLAlchemyNativeRuntimeStore,
)
from dimoo_run.core.config import Settings
from dimoo_run.deployments.instances import AgentInstanceRecord, AgentInstanceRegistry
from dimoo_run.deployments.service import DeploymentRecord, DeploymentRuntimeControlService
from dimoo_run.domain.enums import RunStatus, TaskStatus
from dimoo_run.domain.models import WorkerSnapshot
from dimoo_run.persistence.database import Base, create_session_factory

ACTIVE_TASK_STATUSES = {TaskStatus.leased, TaskStatus.running}


@dataclass(kw_only=True)
class WorkerRecord:
    id: int | None = None
    worker_id: str
    tenant_id: int
    project_id: int
    environment: str
    queues: list[str] = field(default_factory=lambda: ["default"])
    version: str = "unknown"
    capacity: int = 1
    status: str = "idle"
    drain_status: str = "active"
    heartbeat_at: datetime | None = None
    last_error: str | None = None
    restart_requested_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(
        self,
        *,
        status: str,
        heartbeat_at: datetime,
        queues: list[str] | None = None,
        version: str | None = None,
        capacity: int | None = None,
        last_error: str | None = None,
    ) -> None:
        self.status = status
        self.heartbeat_at = heartbeat_at
        if queues is not None:
            self.queues = sorted({*queues}) or ["default"]
        if version is not None:
            self.version = version
        if capacity is not None and capacity > 0:
            self.capacity = capacity
        if last_error is not None:
            self.last_error = last_error


class WorkerRegistry:
    def __init__(self, *, database_url: str | None = None) -> None:
        self._workers: dict[str, WorkerRecord] = {}
        self._database_url = database_url

    def heartbeat(
        self,
        *,
        worker_id: str,
        tenant_id: int,
        project_id: int,
        environment: str,
        status: str,
        queues: list[str] | None = None,
        version: str | None = None,
        capacity: int | None = None,
        last_error: str | None = None,
        now: datetime | None = None,
    ) -> WorkerRecord:
        record = self.get(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        ) or WorkerRecord(
            worker_id=worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        record.tenant_id = tenant_id
        record.project_id = project_id
        record.environment = environment
        record.touch(
            status=status,
            heartbeat_at=now or datetime.now(UTC),
            queues=queues,
            version=version,
            capacity=capacity,
            last_error=last_error,
        )
        if self._persist(record):
            persisted = self.get(
                worker_id,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
            )
            return persisted or record
        self._workers[worker_id] = record
        return record

    def ensure(
        self,
        *,
        worker_id: str,
        tenant_id: int,
        project_id: int,
        environment: str,
        status: str = "unknown",
        version: str = "unknown",
        capacity: int = 1,
    ) -> WorkerRecord:
        existing = self.get(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        if existing is not None:
            return existing
        record = WorkerRecord(
            worker_id=worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
            status=status,
            version=version,
            capacity=max(1, capacity),
        )
        if self._persist(record):
            return self.get(
                worker_id,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
            ) or record
        self._workers[worker_id] = record
        return record

    def get(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord | None:
        db_record = self._db_get(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        if db_record is not None:
            return db_record
        record = self._workers.get(worker_id)
        if record is None:
            return None
        if tenant_id is not None and record.tenant_id != tenant_id:
            return None
        if project_id is not None and record.project_id != project_id:
            return None
        if environment is not None and record.environment != environment:
            return None
        return record

    def list(
        self,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> builtins.list[WorkerRecord]:
        workers = {
            worker.worker_id: worker
            for worker in self._db_list(
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
            )
        }
        for worker in self._workers.values():
            if tenant_id is not None and worker.tenant_id != tenant_id:
                continue
            if project_id is not None and worker.project_id != project_id:
                continue
            if environment is not None and worker.environment != environment:
                continue
            workers.setdefault(worker.worker_id, worker)
        return sorted(workers.values(), key=lambda item: item.worker_id)

    def drain(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord:
        return self._set_drain_status(
            worker_id,
            "draining",
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )

    def undrain(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord:
        return self._set_drain_status(
            worker_id,
            "active",
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )

    def quarantine(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord:
        return self._set_drain_status(
            worker_id,
            "quarantined",
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )

    def request_restart(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
        now: datetime | None = None,
    ) -> WorkerRecord:
        worker = self._require(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        restart_requested_at = now or datetime.now(UTC)
        snapshot = self._db_get(
            worker_id,
            tenant_id=worker.tenant_id,
            project_id=worker.project_id,
            environment=worker.environment,
        )
        if snapshot is not None:
            if self._with_session(
                lambda session: self._db_request_restart(
                    session,
                    worker_id=worker_id,
                    tenant_id=worker.tenant_id,
                    project_id=worker.project_id,
                    environment=worker.environment,
                    restart_requested_at=restart_requested_at,
                )
            ):
                return self._require(
                    worker_id,
                    tenant_id=worker.tenant_id,
                    project_id=worker.project_id,
                    environment=worker.environment,
                )
        worker.restart_requested_at = restart_requested_at
        self._workers[worker_id] = worker
        return worker

    def reset(self) -> None:
        self._workers.clear()
        self._with_session(self._db_reset)

    def _require(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord:
        worker = self.get(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        if worker is None:
            raise KeyError(worker_id)
        return worker

    def _set_drain_status(
        self,
        worker_id: str,
        drain_status: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord:
        worker = self._require(
            worker_id,
            tenant_id=tenant_id,
            project_id=project_id,
            environment=environment,
        )
        snapshot = self._db_get(
            worker_id,
            tenant_id=worker.tenant_id,
            project_id=worker.project_id,
            environment=worker.environment,
        )
        if snapshot is not None:
            if self._with_session(
                lambda session: self._db_set_drain_status(
                    session,
                    worker_id=worker_id,
                    tenant_id=worker.tenant_id,
                    project_id=worker.project_id,
                    environment=worker.environment,
                    drain_status=drain_status,
                )
            ):
                return self._require(
                    worker_id,
                    tenant_id=worker.tenant_id,
                    project_id=worker.project_id,
                    environment=worker.environment,
                )
        worker.drain_status = drain_status
        self._workers[worker_id] = worker
        return worker

    def _persist(self, record: WorkerRecord) -> bool:
        return self._with_session(lambda session: self._db_upsert(session, record))

    def _with_session(self, operation: Any) -> bool:
        try:
            session_factory = self._session_factory()
        except Exception:
            return False
        if session_factory is None:
            return False
        session = session_factory()
        try:
            operation(session)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def _session_factory(self) -> Any:
        database_url = self._database_url or Settings.from_env().database.url
        _ensure_worker_snapshot_table(database_url)
        return _worker_registry_session_factory(database_url)

    def _db_get(
        self,
        worker_id: str,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> WorkerRecord | None:
        session_factory = self._session_factory_or_none()
        if session_factory is None:
            return None
        session = session_factory()
        try:
            query = session.query(WorkerSnapshot).filter(
                WorkerSnapshot.worker_id == worker_id,
                WorkerSnapshot.is_deleted.is_(False),
            )
            if tenant_id is not None:
                query = query.filter(WorkerSnapshot.tenant_id == tenant_id)
            if project_id is not None:
                query = query.filter(WorkerSnapshot.project_id == project_id)
            if environment is not None:
                query = query.filter(WorkerSnapshot.environment == environment)
            snapshot = (
                query.order_by(
                    WorkerSnapshot.updated_at.desc(),
                    WorkerSnapshot.id.desc(),
                ).first()
            )
            return _record_from_snapshot(snapshot) if snapshot is not None else None
        except Exception:
            return None
        finally:
            session.close()

    def _db_list(
        self,
        *,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
    ) -> builtins.list[WorkerRecord]:
        session_factory = self._session_factory_or_none()
        if session_factory is None:
            return []
        session = session_factory()
        try:
            query = session.query(WorkerSnapshot).filter(WorkerSnapshot.is_deleted.is_(False))
            if tenant_id is not None:
                query = query.filter(WorkerSnapshot.tenant_id == tenant_id)
            if project_id is not None:
                query = query.filter(WorkerSnapshot.project_id == project_id)
            if environment is not None:
                query = query.filter(WorkerSnapshot.environment == environment)
            return [_record_from_snapshot(snapshot) for snapshot in query.all()]
        except Exception:
            return []
        finally:
            session.close()

    def _session_factory_or_none(self) -> Any:
        try:
            return self._session_factory()
        except Exception:
            return None

    @staticmethod
    def _db_upsert(session: Any, record: WorkerRecord) -> None:
        snapshot = (
            session.query(WorkerSnapshot)
            .filter(
                WorkerSnapshot.tenant_id == record.tenant_id,
                WorkerSnapshot.project_id == record.project_id,
                WorkerSnapshot.environment == record.environment,
                WorkerSnapshot.worker_id == record.worker_id,
                WorkerSnapshot.is_deleted.is_(False),
            )
            .one_or_none()
        )
        if snapshot is None:
            snapshot = WorkerSnapshot(
                tenant_id=record.tenant_id,
                project_id=record.project_id,
                environment=record.environment,
                worker_id=record.worker_id,
            )
            session.add(snapshot)
        snapshot.status = record.status
        snapshot.drain_status = record.drain_status
        snapshot.version = record.version
        snapshot.capacity = max(1, record.capacity)
        snapshot.heartbeat_at = record.heartbeat_at
        snapshot.last_error = record.last_error
        snapshot.restart_requested_at = record.restart_requested_at
        snapshot.metadata_json = {"queues": record.queues, **dict(record.metadata)}

    @staticmethod
    def _db_set_drain_status(
        session: Any,
        *,
        worker_id: str,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
        drain_status: str,
    ) -> None:
        snapshot = (
            session.query(WorkerSnapshot)
            .filter(
                WorkerSnapshot.worker_id == worker_id,
                WorkerSnapshot.is_deleted.is_(False),
            )
        )
        if tenant_id is not None:
            snapshot = snapshot.filter(WorkerSnapshot.tenant_id == tenant_id)
        if project_id is not None:
            snapshot = snapshot.filter(WorkerSnapshot.project_id == project_id)
        if environment is not None:
            snapshot = snapshot.filter(WorkerSnapshot.environment == environment)
        snapshot = snapshot.order_by(
            WorkerSnapshot.updated_at.desc(),
            WorkerSnapshot.id.desc(),
        ).first()
        if snapshot is None:
            raise KeyError(worker_id)
        snapshot.drain_status = drain_status

    @staticmethod
    def _db_request_restart(
        session: Any,
        *,
        worker_id: str,
        tenant_id: int | None = None,
        project_id: int | None = None,
        environment: str | None = None,
        restart_requested_at: datetime,
    ) -> None:
        snapshot = (
            session.query(WorkerSnapshot)
            .filter(
                WorkerSnapshot.worker_id == worker_id,
                WorkerSnapshot.is_deleted.is_(False),
            )
        )
        if tenant_id is not None:
            snapshot = snapshot.filter(WorkerSnapshot.tenant_id == tenant_id)
        if project_id is not None:
            snapshot = snapshot.filter(WorkerSnapshot.project_id == project_id)
        if environment is not None:
            snapshot = snapshot.filter(WorkerSnapshot.environment == environment)
        snapshot = snapshot.order_by(
            WorkerSnapshot.updated_at.desc(),
            WorkerSnapshot.id.desc(),
        ).first()
        if snapshot is None:
            raise KeyError(worker_id)
        snapshot.restart_requested_at = restart_requested_at

    @staticmethod
    def _db_reset(session: Any) -> None:
        session.query(WorkerSnapshot).delete()


@lru_cache(maxsize=4)
def _worker_registry_session_factory(database_url: str) -> Any:
    return create_session_factory(database_url)


@lru_cache(maxsize=4)
def _ensure_worker_snapshot_table(database_url: str) -> None:
    session_factory = create_session_factory(database_url)
    session = session_factory()
    try:
        Base.metadata.create_all(
            session.get_bind(),
            tables=[cast(Any, WorkerSnapshot.__table__)],
        )
    finally:
        session.close()


def _record_from_snapshot(snapshot: WorkerSnapshot) -> WorkerRecord:
    metadata = dict(snapshot.metadata_json or {})
    queues = metadata.pop("queues", ["default"])
    normalized_queues = [str(item) for item in queues] if isinstance(queues, list) else ["default"]
    return WorkerRecord(
        id=snapshot.id,
        worker_id=snapshot.worker_id,
        tenant_id=snapshot.tenant_id,
        project_id=snapshot.project_id,
        environment=snapshot.environment,
        queues=sorted({*normalized_queues}) or ["default"],
        version=snapshot.version,
        capacity=max(1, snapshot.capacity),
        status=snapshot.status,
        drain_status=snapshot.drain_status,
        heartbeat_at=snapshot.heartbeat_at,
        last_error=snapshot.last_error,
        restart_requested_at=snapshot.restart_requested_at,
        metadata=metadata,
    )


_default_worker_registry = WorkerRegistry()


def default_worker_registry() -> WorkerRegistry:
    return _default_worker_registry


def reset_worker_registry() -> None:
    _default_worker_registry.reset()


def build_worker_health_views(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    workers: WorkerRegistry,
    tenant_id: int,
    project_id: int,
    environment: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or datetime.now(UTC)
    runs = runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
    tasks = runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
    scoped_deployments = {
        deployment.id: deployment
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    }
    instances = _scoped_instances(
        deployments.instances,
        deployment_ids=set(scoped_deployments),
        tenant_id=tenant_id,
        project_id=project_id,
    )
    registry_workers = workers.list(
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    relevant_worker_ids = {
        *[worker.worker_id for worker in registry_workers],
        *[instance.worker_id for instance in instances],
    }
    scoped_run_ids = {
        run.id for run in runs if run.deployment_id in scoped_deployments
    }
    all_run_ids = {run.id for run in runs}
    scoped_tasks = [
        task
        for task in tasks
        if _task_is_in_scope(
            task,
            scoped_run_ids=scoped_run_ids,
            all_run_ids=all_run_ids,
            scoped_worker_ids=relevant_worker_ids,
        )
    ]
    task_groups = _tasks_by_worker(scoped_tasks)
    instance_groups = _instances_by_worker(instances)
    worker_map = {worker.worker_id: worker for worker in registry_workers}
    for worker_id in sorted({*task_groups, *instance_groups}):
        worker_map.setdefault(
            worker_id,
            WorkerRecord(
                worker_id=worker_id,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                status="unknown",
            ),
        )
    views: list[dict[str, Any]] = []
    for worker in sorted(worker_map.values(), key=lambda item: item.worker_id):
        worker_tasks = task_groups.get(worker.worker_id, [])
        worker_instances = instance_groups.get(worker.worker_id, [])
        deployment_ids = sorted({instance.deployment_id for instance in worker_instances})
        active_runs = {
            run.id
            for run in runs
            if run.status in {RunStatus.pending, RunStatus.running}
            and run.deployment_id in deployment_ids
        }
        active_attempts = sum(
            1 for task in worker_tasks if task.status in ACTIVE_TASK_STATUSES
        )
        retrying_tasks = sum(1 for task in worker_tasks if task.status == TaskStatus.retrying)
        dead_letter_tasks = sum(
            1 for task in worker_tasks if task.status == TaskStatus.dead_letter
        )
        heartbeat_at = _normalize_datetime(worker.heartbeat_at)
        heartbeat_age_seconds = (
            (current - heartbeat_at).total_seconds()
            if heartbeat_at is not None
            else None
        )
        liveness = "alive"
        if heartbeat_age_seconds is None or heartbeat_age_seconds > 120:
            liveness = "offline"
        elif heartbeat_age_seconds > 45:
            liveness = "stale"
        readiness = "ready"
        if worker.drain_status == "quarantined":
            readiness = "blocked"
        elif worker.drain_status == "draining":
            readiness = "draining"
        elif active_attempts >= worker.capacity:
            readiness = "saturated"
        elif liveness != "alive":
            readiness = "degraded"
        last_error = worker.last_error or next(
            (
                _task_error(task)
                for task in reversed(worker_tasks)
                if _task_error(task) is not None
            ),
            None,
        ) or next(
            (instance.error for instance in reversed(worker_instances) if instance.error),
            None,
        )
        views.append(
            {
                "worker_id": worker.worker_id,
                "environment": worker.environment,
                "status": worker.status,
                "drain_status": worker.drain_status,
                "version": worker.version,
                "queues": sorted({*worker.queues, *(task.queue for task in worker_tasks)}),
                "capacity": worker.capacity,
                "active_attempts": active_attempts,
                "active_runs": len(active_runs),
                "heartbeat_age_seconds": heartbeat_age_seconds,
                "last_error": last_error,
                "liveness": liveness,
                "readiness": readiness,
                "retrying_tasks": retrying_tasks,
                "dead_letter_tasks": dead_letter_tasks,
                "deployment_ids": deployment_ids,
                "restart_requested_at": _isoformat(worker.restart_requested_at),
            }
        )
    return views


def build_worker_detail_view(
    *,
    worker_id: str,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    workers: WorkerRegistry,
    tenant_id: int,
    project_id: int,
    environment: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    health = next(
        (
            item
            for item in build_worker_health_views(
                runtime=runtime,
                deployments=deployments,
                workers=workers,
                tenant_id=tenant_id,
                project_id=project_id,
                environment=environment,
                now=now,
            )
            if item["worker_id"] == worker_id
        ),
        None,
    )
    if health is None:
        raise KeyError(worker_id)
    tasks = _scoped_tasks_for_worker(
        runtime=runtime,
        deployments=deployments,
        worker_id=worker_id,
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    active_tasks = [task for task in tasks if task.status in ACTIVE_TASK_STATUSES]
    active_run_ids = sorted({task.run_id for task in active_tasks})
    health["scoped_tasks"] = tasks
    health["active_task_ids"] = [task.id for task in active_tasks]
    health["active_run_ids"] = active_run_ids
    return health


def build_agent_instance_views(
    *,
    deployments: DeploymentRuntimeControlService,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[dict[str, Any]]:
    scoped_deployments = {
        deployment.id: deployment
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    }
    failed_runs_by_deployment: dict[int, int] = defaultdict(int)
    for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id):
        if run.deployment_id is not None and run.status == RunStatus.failed:
            failed_runs_by_deployment[run.deployment_id] += 1
    views: list[dict[str, Any]] = []
    for instance in _scoped_instances(
        deployments.instances,
        deployment_ids=set(scoped_deployments),
        tenant_id=tenant_id,
        project_id=project_id,
    ):
        deployment = scoped_deployments.get(instance.deployment_id)
        if deployment is None:
            continue
        config_hash = _runtime_config_hash(instance=instance, deployment=deployment)
        views.append(
            {
                "id": instance.id,
                "deployment_id": instance.deployment_id,
                "environment": deployment.environment,
                "agent_id": instance.agent_id,
                "agent_version_id": instance.agent_version_id,
                "worker_id": instance.worker_id,
                "status": instance.status,
                "active_runs": instance.running_runs,
                "recent_failures": int(
                    instance.metadata.get(
                        "recent_failures",
                        failed_runs_by_deployment.get(instance.deployment_id, 0),
                    )
                ),
                "concurrency_limit": int(
                    instance.metadata.get("concurrency_limit", max(1, deployment.replicas))
                ),
                "runtime_config_hash": config_hash,
                "execution_profile_id": instance.execution_profile_id,
                "cache_key": instance.cache_key,
                "loaded_at": _isoformat(instance.loaded_at),
                "heartbeat_at": _isoformat(instance.heartbeat_at),
                "last_error": instance.error,
                "deployment_desired_status": deployment.desired_status.value,
                "deployment_runtime_status": deployment.runtime_status.value,
            }
        )
    return sorted(views, key=lambda item: (item["deployment_id"], item["id"]))


def build_capacity_summary(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    workers: WorkerRegistry,
    tenant_id: int,
    project_id: int,
    environment: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    tasks = runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
    scoped_workers = workers.list(
        tenant_id=tenant_id,
        project_id=project_id,
        environment=environment,
    )
    scoped_worker_ids = {worker.worker_id for worker in scoped_workers}
    deployment_ids = {
        deployment.id
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    }
    runs = {
        run.id: run
        for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
        if run.deployment_id in deployment_ids
    }
    all_run_ids = {run.id for run in runtime.list_runs(tenant_id=tenant_id, project_id=project_id)}
    scoped_tasks = [
        task
        for task in tasks
        if _task_is_in_scope(
            task,
            scoped_run_ids=set(runs),
            all_run_ids=all_run_ids,
            scoped_worker_ids=scoped_worker_ids,
        )
    ]
    queue_groups: dict[str, list[NativeTask]] = defaultdict(list)
    for task in scoped_tasks:
        queue_groups[task.queue].append(task)
    queue_breakdown: list[dict[str, Any]] = []
    queue_backlog = 0
    active_attempts = 0
    retry_pressure = 0
    dead_letter_pressure = 0
    critical_attempts = 0
    for queue_name, queue_tasks in sorted(queue_groups.items()):
        queued = sum(1 for task in queue_tasks if task.status == TaskStatus.queued)
        leased = sum(1 for task in queue_tasks if task.status == TaskStatus.leased)
        running = sum(1 for task in queue_tasks if task.status == TaskStatus.running)
        retrying = sum(1 for task in queue_tasks if task.status == TaskStatus.retrying)
        dead_letter = sum(1 for task in queue_tasks if task.status == TaskStatus.dead_letter)
        oldest_created_at = min((task.created_at for task in queue_tasks), default=None)
        queue_backlog += queued + retrying
        active_attempts += leased + running
        retry_pressure += retrying
        dead_letter_pressure += dead_letter
        critical_attempts += sum(1 for task in queue_tasks if is_critical_attempt(task))
        queue_breakdown.append(
            {
                "queue": queue_name,
                "queue_backlog": queued + retrying,
                "leased": leased,
                "running": running,
                "retrying": retrying,
                "dead_letter": dead_letter,
                "oldest_task_age_seconds": (
                    (current - oldest_created_at).total_seconds()
                    if oldest_created_at is not None
                    else None
                ),
            }
        )
    total_capacity = sum(
        worker.capacity
        for worker in scoped_workers
        if worker.drain_status != "quarantined"
    )
    if total_capacity <= 0:
        total_capacity = max(
            1,
            sum(
                deployment.replicas
                for deployment in deployments.deployments.list(
                    tenant_id=tenant_id,
                    project_id=project_id,
                )
                if deployment.environment == environment
            ),
        )
    saturation_ratio = active_attempts / total_capacity if total_capacity else 0.0
    time_to_drain_seconds = int(
        ((active_attempts * 45) + (queue_backlog * 30)) / max(total_capacity, 1)
    )
    recommended_action = "steady_state"
    recommended_reason = "Workers and queues are within expected operating bounds."
    if dead_letter_pressure > 0:
        recommended_action = "investigate_dead_letters"
        recommended_reason = "Dead-letter pressure is non-zero and requires operator review."
    elif critical_attempts > 0:
        recommended_action = "hold_drain"
        recommended_reason = (
            "Critical attempts are still active. Keep drains blocked until they clear."
        )
    elif saturation_ratio >= 1 or queue_backlog > total_capacity * 2:
        recommended_action = "scale_out"
        recommended_reason = "Queue backlog exceeds current worker capacity."
    elif any(worker.drain_status == "quarantined" for worker in scoped_workers):
        recommended_action = "replace_quarantined_worker"
        recommended_reason = "A worker is quarantined and should be replaced or restarted."
    return {
        "queue_backlog": queue_backlog,
        "active_attempts": active_attempts,
        "total_capacity": total_capacity,
        "saturation_ratio": saturation_ratio,
        "time_to_drain_seconds": time_to_drain_seconds,
        "retry_pressure": retry_pressure,
        "dead_letter_pressure": dead_letter_pressure,
        "recommended_action": recommended_action,
        "recommended_reason": recommended_reason,
        "active_workers": sum(1 for worker in scoped_workers if worker.drain_status == "active"),
        "draining_workers": sum(
            1 for worker in scoped_workers if worker.drain_status == "draining"
        ),
        "quarantined_workers": sum(
            1 for worker in scoped_workers if worker.drain_status == "quarantined"
        ),
        "critical_attempts": critical_attempts,
        "queues": queue_breakdown,
    }


def build_worker_actions(
    *,
    worker: WorkerRecord,
    tasks: list[NativeTask],
    actor_scopes: frozenset[str],
) -> list[dict[str, Any]]:
    has_permission = "*" in actor_scopes or "agent:deploy" in actor_scopes
    critical_attempts = sum(1 for task in tasks if is_critical_attempt(task))
    active_attempts = sum(1 for task in tasks if task.status in ACTIVE_TASK_STATUSES)
    actions: list[dict[str, Any]] = []
    for action, label in (
        ("drain", "Drain worker"),
        ("undrain", "Resume scheduling"),
        ("quarantine", "Quarantine worker"),
        ("restart-request", "Request restart"),
    ):
        disabled_reasons: list[str] = []
        if not has_permission:
            disabled_reasons.append("Current actor lacks agent:deploy permission.")
        if action == "drain":
            if worker.drain_status != "active":
                disabled_reasons.append("Worker must be active before it can drain.")
            if critical_attempts > 0:
                disabled_reasons.append(
                    "Worker has active critical attempt and cannot drain safely."
                )
        elif action == "undrain" and worker.drain_status != "draining":
            disabled_reasons.append("Worker must be draining before it can resume scheduling.")
        elif action == "quarantine":
            if worker.drain_status == "quarantined":
                disabled_reasons.append("Worker is already quarantined.")
            if active_attempts > 0:
                disabled_reasons.append(
                    "Worker still has active attempts and cannot quarantine safely."
                )
        elif action == "restart-request" and worker.restart_requested_at is not None:
            disabled_reasons.append("Worker already has a pending restart request.")
        actions.append(
            {
                "action": action,
                "label": label,
                "available": not disabled_reasons,
                "disabled_reasons": disabled_reasons,
                "required_permissions": ["agent:deploy"],
                "audit_required": True,
            }
        )
    return actions


def is_critical_attempt(task: NativeTask) -> bool:
    reason = task.quota_blocking_reason or {}
    if task.resource_class == "critical":
        return True
    for key in ("risk", "severity", "priority"):
        value = reason.get(key)
        if isinstance(value, str) and value.lower() == "critical":
            return True
    return False


def _scoped_instances(
    registry: AgentInstanceRegistry,
    *,
    deployment_ids: set[int],
    tenant_id: int,
    project_id: int,
) -> list[AgentInstanceRecord]:
    return [
        instance
        for instance in registry.instances.values()
        if instance.tenant_id == tenant_id
        and instance.project_id == project_id
        and instance.deployment_id in deployment_ids
    ]


def _tasks_by_worker(tasks: list[NativeTask]) -> dict[str, list[NativeTask]]:
    grouped: dict[str, list[NativeTask]] = defaultdict(list)
    for task in tasks:
        worker_id = _task_worker_id(task)
        if isinstance(worker_id, str) and worker_id:
            grouped[worker_id].append(task)
    return grouped


def _scoped_tasks_for_worker(
    *,
    runtime: NativeRuntimeStore | SQLAlchemyNativeRuntimeStore,
    deployments: DeploymentRuntimeControlService,
    worker_id: str,
    tenant_id: int,
    project_id: int,
    environment: str,
) -> list[NativeTask]:
    runs = runtime.list_runs(tenant_id=tenant_id, project_id=project_id)
    scoped_deployment_ids = {
        deployment.id
        for deployment in deployments.deployments.list(tenant_id=tenant_id, project_id=project_id)
        if deployment.environment == environment
    }
    scoped_run_ids = {
        run.id for run in runs if run.deployment_id in scoped_deployment_ids
    }
    all_run_ids = {run.id for run in runs}
    return [
        task
        for task in runtime.list_tasks(tenant_id=tenant_id, project_id=project_id)
        if _task_worker_id(task) == worker_id
        and _task_is_in_scope(
            task,
            scoped_run_ids=scoped_run_ids,
            all_run_ids=all_run_ids,
            scoped_worker_ids={worker_id},
        )
    ]


def _task_worker_id(task: NativeTask) -> str | None:
    worker_id = task.worker_id
    return worker_id if isinstance(worker_id, str) and worker_id else None


def _task_is_in_scope(
    task: NativeTask,
    *,
    scoped_run_ids: set[int],
    all_run_ids: set[int],
    scoped_worker_ids: set[str],
) -> bool:
    if task.run_id in scoped_run_ids:
        return True
    worker_id = _task_worker_id(task)
    if worker_id not in scoped_worker_ids:
        return False
    return task.run_id not in all_run_ids


def _instances_by_worker(
    instances: list[AgentInstanceRecord],
) -> dict[str, list[AgentInstanceRecord]]:
    grouped: dict[str, list[AgentInstanceRecord]] = defaultdict(list)
    for instance in instances:
        grouped[instance.worker_id].append(instance)
    return grouped


def _runtime_config_hash(
    *,
    instance: AgentInstanceRecord,
    deployment: DeploymentRecord,
) -> str:
    if isinstance(instance.metadata.get("runtime_config_hash"), str):
        return str(instance.metadata["runtime_config_hash"])
    payload = {
        "deployment_id": deployment.id,
        "agent_version_id": instance.agent_version_id,
        "config": deployment.config_json,
        "execution_profile_id": instance.execution_profile_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()[:12]


def _task_error(task: NativeTask) -> str | None:
    if task.error is None:
        return None
    message = task.error.get("message")
    return str(message) if message else None


def _isoformat(value: datetime | None) -> str | None:
    normalized = _normalize_datetime(value)
    return normalized.isoformat() if normalized is not None else None


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
