from collections.abc import Mapping


class InvalidStateTransitionError(ValueError):
    def __init__(self, *, entity: str, current: str, target: str) -> None:
        self.entity = entity
        self.current = current
        self.target = target
        super().__init__(f"Invalid {entity} transition: {current} -> {target}")


RUN_TRANSITIONS: Mapping[str, set[str]] = {
    "pending": {"running", "cancelled"},
    "running": {"interrupted", "succeeded", "failed", "cancelled", "timeout"},
    "interrupted": {"running", "cancelled", "timeout"},
    "failed": {"running"},
    "timeout": {"running"},
    "succeeded": set(),
    "cancelled": set(),
}

TASK_TRANSITIONS: Mapping[str, set[str]] = {
    "queued": {"leased", "cancelled"},
    "leased": {"running", "queued"},
    "running": {"succeeded", "failed", "retrying", "cancelled", "dead_letter"},
    "retrying": {"queued"},
    "failed": {"retrying", "dead_letter"},
    "succeeded": set(),
    "dead_letter": set(),
    "cancelled": set(),
}

RUN_ATTEMPT_TRANSITIONS: Mapping[str, set[str]] = {
    "running": {"succeeded", "failed", "timeout", "cancelled", "worker_lost"},
    "succeeded": set(),
    "failed": set(),
    "timeout": set(),
    "cancelled": set(),
    "worker_lost": set(),
}


def assert_transition(
    transitions: Mapping[str, set[str]],
    *,
    entity: str,
    current: str,
    target: str,
) -> None:
    if target not in transitions.get(current, set()):
        raise InvalidStateTransitionError(entity=entity, current=current, target=target)


def assert_run_transition(current: str, target: str) -> None:
    assert_transition(RUN_TRANSITIONS, entity="run", current=current, target=target)


def assert_task_transition(current: str, target: str) -> None:
    assert_transition(TASK_TRANSITIONS, entity="task", current=current, target=target)


def assert_run_attempt_transition(current: str, target: str) -> None:
    assert_transition(
        RUN_ATTEMPT_TRANSITIONS,
        entity="run_attempt",
        current=current,
        target=target,
    )
