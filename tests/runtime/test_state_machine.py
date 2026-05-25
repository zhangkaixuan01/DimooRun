import pytest
from dimoo_run.runtime.state_machine import (
    InvalidStateTransitionError,
    assert_run_attempt_transition,
    assert_run_transition,
    assert_task_transition,
)


def test_run_state_machine_allows_retry_from_failed_and_timeout() -> None:
    assert_run_transition("pending", "running")
    assert_run_transition("running", "failed")
    assert_run_transition("failed", "running")
    assert_run_transition("timeout", "running")


def test_run_state_machine_rejects_terminal_overwrite() -> None:
    with pytest.raises(InvalidStateTransitionError):
        assert_run_transition("succeeded", "running")


def test_task_state_machine_allows_lease_retry_and_dead_letter_paths() -> None:
    assert_task_transition("queued", "leased")
    assert_task_transition("leased", "running")
    assert_task_transition("running", "retrying")
    assert_task_transition("retrying", "queued")
    assert_task_transition("failed", "dead_letter")


def test_task_state_machine_rejects_invalid_skip_to_success() -> None:
    with pytest.raises(InvalidStateTransitionError):
        assert_task_transition("queued", "succeeded")


def test_run_attempt_state_machine_has_only_running_as_source() -> None:
    assert_run_attempt_transition("running", "succeeded")

    with pytest.raises(InvalidStateTransitionError):
        assert_run_attempt_transition("failed", "succeeded")
