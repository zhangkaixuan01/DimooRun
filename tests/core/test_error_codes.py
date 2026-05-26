from dimoo_run.core.errors import ERROR_CODES


def test_error_codes_include_runtime_and_governance_codes() -> None:
    assert {
        "api_key_invalid",
        "api_key_scope_denied",
        "model_not_allowed",
        "model_gateway_scope_mismatch",
        "request_scope_required",
        "tool_scope_mismatch",
        "secret_scope_mismatch",
        "stale_fencing_token",
    } <= ERROR_CODES


def test_error_codes_include_api_and_observability_codes() -> None:
    assert {
        "not_implemented",
        "artifact_checksum_mismatch",
        "dataset_scope_mismatch",
        "notification_configuration_invalid",
    } <= ERROR_CODES


def test_error_codes_include_compat_mapping_codes() -> None:
    assert {
        "assistant_not_found",
        "run_not_found",
        "thread_not_found",
    } <= ERROR_CODES
