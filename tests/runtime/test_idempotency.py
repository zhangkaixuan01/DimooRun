import pytest
from dimoo_run.runtime.idempotency import IdempotencyConflictError, IdempotencyStore


def test_idempotency_returns_existing_result_for_same_scope_and_key() -> None:
    store = IdempotencyStore()
    first = store.reserve(
        tenant_id=1,
        project_id=1,
        endpoint="/runs",
        idempotency_key="idem_1",
        request_hash="hash_1",
    )
    store.complete(first.record_id, {"run_id": 1})

    second = store.reserve(
        tenant_id=1,
        project_id=1,
        endpoint="/runs",
        idempotency_key="idem_1",
        request_hash="hash_1",
    )

    assert second.is_replay is True
    assert second.response == {"run_id": 1}


def test_idempotency_scope_includes_endpoint() -> None:
    store = IdempotencyStore()
    first = store.reserve(
        tenant_id=1,
        project_id=1,
        endpoint="/runs",
        idempotency_key="idem_1",
        request_hash="hash_1",
    )
    second = store.reserve(
        tenant_id=1,
        project_id=1,
        endpoint="/runs/run_1/cancel",
        idempotency_key="idem_1",
        request_hash="hash_1",
    )

    assert first.record_id != second.record_id
    assert second.is_replay is False


def test_idempotency_rejects_same_key_with_different_request_hash() -> None:
    store = IdempotencyStore()
    store.reserve(
        tenant_id=1,
        project_id=1,
        endpoint="/runs",
        idempotency_key="idem_1",
        request_hash="hash_1",
    )

    with pytest.raises(IdempotencyConflictError) as exc_info:
        store.reserve(
            tenant_id=1,
            project_id=1,
            endpoint="/runs",
            idempotency_key="idem_1",
            request_hash="hash_2",
        )

    assert exc_info.value.error_code == "idempotency_key_conflict"
