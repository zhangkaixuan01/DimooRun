from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from dimoo_run.adapters.base.contract import CapabilityNotSupportedError
from dimoo_run.adapters.base.versioning import ADAPTER_API_VERSION
from dimoo_run.core.context import RuntimeContext


class ConformanceStatus(StrEnum):
    certified = "certified"
    certified_with_limitations = "certified_with_limitations"
    experimental = "experimental"
    failed = "failed"


@dataclass(frozen=True)
class ConformanceReport:
    framework: str
    framework_version: str
    adapter_api_version: str
    status: ConformanceStatus
    tested_at: datetime
    tests: dict[str, str] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)


async def run_conformance_suite(
    *,
    adapter: Any,
    agent: Any,
    context: RuntimeContext,
    input_data: dict[str, Any],
) -> ConformanceReport:
    tests: dict[str, str] = {}
    failed: list[str] = []

    try:
        await adapter.invoke(agent, input_data, context)
        tests["invoke"] = "passed"
    except Exception as exc:  # pragma: no cover - surfaced in report
        tests["invoke"] = f"failed: {exc}"
        failed.append("invoke")

    try:
        _ = [event async for event in adapter.stream(agent, input_data, context)]
        tests["stream"] = "passed"
    except CapabilityNotSupportedError:
        tests["stream"] = "unsupported"
    except Exception as exc:  # pragma: no cover - surfaced in report
        tests["stream"] = f"failed: {exc}"
        failed.append("stream")

    capabilities = getattr(adapter, "capabilities", None)

    if capabilities is not None and getattr(capabilities, "resume", False):
        try:
            await adapter.resume(agent, context.run_id, input_data, context)
            tests["resume"] = "passed"
        except CapabilityNotSupportedError:
            tests["resume"] = "unsupported"
        except Exception as exc:  # pragma: no cover - surfaced in report
            tests["resume"] = f"failed: {exc}"
            failed.append("resume")
    else:
        tests["resume"] = "unsupported"

    tests["cancel"] = "not_exercised"

    tests["checkpoint"] = (
        "declared"
        if capabilities is not None and getattr(capabilities, "checkpoint", False)
        else "unsupported"
    )
    tests["interrupt"] = "not_exercised"
    tests["idempotency"] = "not_exercised"
    tests["error_mapping"] = "not_exercised"

    if failed:
        status = ConformanceStatus.failed
    elif any(result in {"unsupported", "not_exercised"} for result in tests.values()):
        status = ConformanceStatus.certified_with_limitations
    else:
        status = ConformanceStatus.certified
    version_info = adapter.version_info()

    return ConformanceReport(
        framework=adapter.framework,
        framework_version=version_info.framework_version,
        adapter_api_version=ADAPTER_API_VERSION,
        status=status,
        tested_at=datetime.now(UTC),
        tests=tests,
        failed=failed,
    )
