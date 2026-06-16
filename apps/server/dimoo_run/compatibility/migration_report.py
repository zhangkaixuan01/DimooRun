from typing import Any

_SUPPORTED_FRAMEWORKS = {"langgraph"}
_SUPPORTED_ADAPTERS = {"langgraph"}
_SUPPORTED_CAPABILITIES = {
    "assistants",
    "threads",
    "runs",
    "cancel",
    "join",
    "stream",
    "last_event_replay",
    "checkpoints",
}
_SUPPORTED_STREAMING_MODES = {"events", "updates"}


def _hosted_deployments_remediation() -> dict[str, Any]:
    return {
        "capability": "hosted_deployments",
        "reason": "compatibility_not_supported",
        "severity": "manual_migration_required",
        "target_files": ["dimoorun.yaml", "manifest.yaml"],
        "recommended_action": "Use native deployments for hosted runtime behavior",
        "verification_command": "uv run dimoorun deployment create --help",
        "native_route": "/deployments",
    }


def _stream_mode_remediation(mode: str) -> dict[str, Any]:
    return {
        "capability": f"stream:{mode}",
        "reason": "compatibility_not_supported",
        "severity": "configuration_change_required",
        "target_files": ["dimoorun.yaml"],
        "recommended_action": "Use event or update streaming modes in the compatibility bridge",
        "verification_command": "uv run pytest tests/compat/test_langgraph_compat_api.py -q",
        "native_route": "/compatibility",
    }


def build_migration_report(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload or {}
    framework = str(data.get("framework") or "langgraph")
    adapter = str(data.get("adapter") or framework)
    capabilities = _normalize_strings(data.get("capabilities"))
    streaming_modes = _normalize_strings(data.get("streaming_modes"))
    required_secrets = _normalize_strings(data.get("required_secrets"))
    custom_tools = _normalize_strings(data.get("custom_tools"))
    uses_checkpointing = bool(data.get("uses_checkpointing"))
    requires_interrupts = bool(data.get("requires_interrupts"))

    unsupported_capabilities = []
    remediation_steps: list[dict[str, Any]] = []
    for capability in capabilities:
        if capability not in _SUPPORTED_CAPABILITIES:
            entry = {
                "capability": capability,
                "reason": "compatibility_not_supported",
                "recommended_workaround": (
                    "Use native DimooRun runtime semantics for this feature."
                ),
            }
            unsupported_capabilities.append(entry)
            if capability == "hosted_deployments":
                remediation_steps.append(_hosted_deployments_remediation())

    unsupported_streaming_modes = [
        mode for mode in streaming_modes if mode not in _SUPPORTED_STREAMING_MODES
    ]
    for mode in unsupported_streaming_modes:
        unsupported_capabilities.append(
            {
                "capability": f"stream:{mode}",
                "reason": "compatibility_not_supported",
                "recommended_workaround": (
                    "Use event or update streaming modes in the compatibility bridge."
                ),
            }
        )
        remediation_steps.append(_stream_mode_remediation(mode))

    required_config = [
        "project.name",
        "project.tenant",
        "agents[].manifest",
        "deployments[].agent_version_id",
        "execution_profiles.default",
    ]
    if required_secrets:
        required_config.append("secrets provider configuration")
    if custom_tools:
        required_config.append("policies.tool_approval")
    if uses_checkpointing:
        required_config.append("checkpoint runtime store")
    if requires_interrupts:
        required_config.append("human task and policy approval workflow")

    governance_implications = [
        "Compatibility requests still require tenant and project scoped authentication.",
        "Policy Engine, secret provider, model gateway, and audit logging remain enforced.",
        "Native Run, Task, Event, and deployment state machines remain the source of truth.",
    ]

    recommended_actions = [
        "Validate the target deployment binding before switching traffic.",
        "Run the compatibility explorer to confirm native Run and Task creation.",
    ]
    if required_secrets:
        recommended_actions.append("Map required secret references into DimooRun secret providers.")
    if uses_checkpointing:
        recommended_actions.append(
            "Verify checkpoint and replay expectations against the native runtime store."
        )
    if unsupported_capabilities:
        recommended_actions.append(
            "Review unsupported capability explanations before migration sign-off."
        )

    if framework not in _SUPPORTED_FRAMEWORKS:
        overall_status = "blocked"
        blocked_reason = "framework_not_supported"
    elif adapter not in _SUPPORTED_ADAPTERS or adapter != framework:
        overall_status = "blocked"
        blocked_reason = "adapter_runtime_mismatch"
    elif unsupported_capabilities:
        overall_status = "migration_required"
        blocked_reason = None
    else:
        overall_status = "compatible"
        blocked_reason = None

    return {
        "framework": framework,
        "adapter": adapter,
        "overall_status": overall_status,
        "blocked_reason": blocked_reason,
        "unsupported_capabilities": unsupported_capabilities,
        "required_dimoorun_config": required_config,
        "adapter_contract_version": "1.0",
        "checkpoint_requirements": {
            "required": uses_checkpointing,
            "mode": "native_runtime_store" if uses_checkpointing else "optional",
        },
        "streaming_support": {
            "requested_modes": streaming_modes,
            "supported_modes": sorted(_SUPPORTED_STREAMING_MODES),
            "unsupported_modes": unsupported_streaming_modes,
            "last_event_id_replay": True,
        },
        "governance_implications": governance_implications,
        "recommended_actions": recommended_actions,
        "remediation_steps": remediation_steps,
    }


def _normalize_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]
