from dimoo_run.scheduler.in_memory import InMemoryTaskBackend


class LeaseReaper:
    def __init__(self, backend: InMemoryTaskBackend) -> None:
        self.backend = backend

    def reap(self) -> list[str]:
        before = {
            task_id
            for task_id, task in self.backend.tasks.items()
            if task.status == "leased" and task.leased_until is not None
        }
        self.backend.reap_expired_leases()
        return [
            task_id
            for task_id in before
            if self.backend.tasks[task_id].status == "queued"
            and self.backend.tasks[task_id].worker_id is None
        ]
