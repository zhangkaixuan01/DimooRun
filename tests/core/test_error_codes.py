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
