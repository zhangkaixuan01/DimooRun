from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version

ADAPTER_API_VERSION = "1.0"
MANIFEST_SCHEMA_VERSION = "1.0"
CAPABILITY_SCHEMA_VERSION = "1.0"
EVENT_SCHEMA_VERSION = "1.0"
RUNTIME_CONTEXT_VERSION = "1.0"


class CompatibilityStatus(StrEnum):
    compatible = "compatible"
    compatible_with_warning = "compatible_with_warning"
    migration_required = "migration_required"
    unsupported = "unsupported"


@dataclass(frozen=True)
class AdapterVersionInfo:
    framework: str
    framework_version: str
    adapter_api_version: str = ADAPTER_API_VERSION
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION
    capability_schema_version: str = CAPABILITY_SCHEMA_VERSION
    event_schema_version: str = EVENT_SCHEMA_VERSION
    runtime_context_version: str = RUNTIME_CONTEXT_VERSION
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def get_package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "unknown"


def build_version_info(framework: str, package_name: str) -> AdapterVersionInfo:
    return AdapterVersionInfo(
        framework=framework,
        framework_version=get_package_version(package_name),
    )


def check_adapter_compatibility(
    *,
    expected_adapter_api_version: str,
    actual_adapter_api_version: str,
) -> CompatibilityStatus:
    if expected_adapter_api_version == actual_adapter_api_version:
        return CompatibilityStatus.compatible
    expected_major = expected_adapter_api_version.split(".", maxsplit=1)[0]
    actual_major = actual_adapter_api_version.split(".", maxsplit=1)[0]
    if expected_major == actual_major:
        return CompatibilityStatus.compatible_with_warning
    return CompatibilityStatus.migration_required
