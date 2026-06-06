import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

SUPPORTED_RUNTIME_PAIRS = {
    "langgraph": "langgraph",
    "langchain-agent": "langchain-agent",
    "deepagents": "deepagents",
}
SUPPORTED_CAPABILITIES = {"invoke", "stream", "streaming"}


@dataclass(frozen=True)
class PackageValidationError:
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class PackageValidationResult:
    status: Literal["valid", "invalid"]
    ready: bool
    validation_token: str | None
    errors: list[PackageValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_secret_refs: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    next_action: str = "fix_validation_errors"


@dataclass(frozen=True)
class PackageValidationRequest:
    package_uri: str
    framework: str
    adapter: str
    entrypoint: str
    manifest: dict[str, Any]
    required_secret_refs: list[str]


def validate_package(request: PackageValidationRequest) -> PackageValidationResult:
    errors: list[PackageValidationError] = []
    warnings: list[str] = []

    if not _package_uri_allowed(request.package_uri):
        errors.append(
            PackageValidationError(
                field="package_uri",
                code="package_uri_not_allowed",
                message="Package URI must use an allowed oci://, file://, or local path policy.",
            )
        )

    expected_framework = SUPPORTED_RUNTIME_PAIRS.get(request.adapter)
    if expected_framework != request.framework:
        errors.append(
            PackageValidationError(
                field="runtime",
                code="unsupported_runtime_pair",
                message="Framework and adapter must use a supported runtime pair.",
            )
        )

    if ":" not in request.entrypoint or any(not part for part in request.entrypoint.split(":", 1)):
        errors.append(
            PackageValidationError(
                field="entrypoint",
                code="invalid_entrypoint",
                message="Entrypoint must use module:function format.",
            )
        )

    runtime = request.manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append(
            PackageValidationError(
                field="manifest.runtime",
                code="manifest_runtime_missing",
                message="Manifest must include runtime metadata.",
            )
        )
        runtime = {}

    runtime_framework = runtime.get("framework", request.framework)
    runtime_adapter = runtime.get("adapter", request.adapter)
    runtime_entrypoint = runtime.get("entrypoint")
    if (
        runtime_framework != request.framework
        or runtime_adapter != request.adapter
        or runtime_entrypoint != request.entrypoint
    ):
        errors.append(
            PackageValidationError(
                field="manifest.runtime",
                code="manifest_runtime_mismatch",
                message=(
                    "Manifest runtime must match the requested framework, adapter, "
                    "and entrypoint."
                ),
            )
        )

    manifest_secret_refs = _manifest_secret_refs(request.manifest)
    missing_secret_refs = [
        ref for ref in request.required_secret_refs if ref not in manifest_secret_refs
    ]
    for missing in missing_secret_refs:
        errors.append(
            PackageValidationError(
                field="required_secret_refs",
                code="required_secret_missing",
                message=f"Required secret reference is missing from manifest: {missing}",
            )
        )

    capabilities = request.manifest.get("capabilities")
    if capabilities is None:
        capabilities = {}
        warnings.append("Manifest does not declare capabilities.")
    if not isinstance(capabilities, dict):
        errors.append(
            PackageValidationError(
                field="manifest.capabilities",
                code="invalid_capabilities",
                message="Manifest capabilities must be a JSON object.",
            )
        )
        capabilities = {}
    for capability in capabilities:
        if capability not in SUPPORTED_CAPABILITIES:
            errors.append(
                PackageValidationError(
                    field="manifest.capabilities",
                    code="unsupported_capability",
                    message=(
                        "Capability is not supported by the runtime compatibility policy: "
                        f"{capability}"
                    ),
                )
            )

    warnings.extend(_dependency_warnings(request.manifest))

    if errors:
        return PackageValidationResult(
            status="invalid",
            ready=False,
            validation_token=None,
            errors=errors,
            warnings=warnings,
            missing_secret_refs=missing_secret_refs,
            capabilities=capabilities,
            next_action="fix_validation_errors",
        )
    return PackageValidationResult(
        status="valid",
        ready=True,
        validation_token=validation_token(
            package_uri=request.package_uri,
            framework=request.framework,
            adapter=request.adapter,
            entrypoint=request.entrypoint,
            manifest=request.manifest,
        ),
        warnings=warnings,
        missing_secret_refs=[],
        capabilities=capabilities,
        next_action="create_ready_agent_version",
    )


def validation_token(
    *,
    package_uri: str,
    framework: str,
    adapter: str,
    entrypoint: str,
    manifest: dict[str, Any],
) -> str:
    token_payload = {
        "package_uri": package_uri,
        "framework": framework,
        "adapter": adapter,
        "entrypoint": entrypoint,
        "manifest": _manifest_without_validation_token(manifest),
    }
    encoded = json.dumps(token_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "pkgval_" + hashlib.sha256(encoded).hexdigest()[:32]


def manifest_has_valid_token(
    *,
    package_uri: str,
    framework: str,
    adapter: str,
    entrypoint: str,
    manifest: dict[str, Any],
) -> bool:
    token = manifest.get("validation_token")
    if not isinstance(token, str):
        return False
    return token == validation_token(
        package_uri=package_uri,
        framework=framework,
        adapter=adapter,
        entrypoint=entrypoint,
        manifest=manifest,
    )


def _manifest_secret_refs(manifest: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    secrets = manifest.get("secrets", [])
    if isinstance(secrets, list):
        for item in secrets:
            if isinstance(item, str):
                refs.add(item)
            elif isinstance(item, dict) and isinstance(item.get("ref"), str):
                refs.add(item["ref"])
    required_secrets = manifest.get("required_secrets", [])
    if isinstance(required_secrets, list):
        refs.update(item for item in required_secrets if isinstance(item, str))
    return refs


def _dependency_warnings(manifest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    dependencies = manifest.get("dependencies", [])
    if dependencies in (None, []):
        return warnings
    if not isinstance(dependencies, list):
        return ["Manifest dependencies should be a list of objects with name and version."]
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            warnings.append(
                f"Dependency entry must be an object with name and version: {dependency}"
            )
            continue
        name = dependency.get("name")
        version = dependency.get("version")
        if not isinstance(name, str) or not name:
            warnings.append("Dependency entry must include a non-empty name.")
            continue
        if not isinstance(version, str) or not version:
            warnings.append(f"Dependency {name} does not declare a version.")
    return warnings


def _package_uri_allowed(package_uri: str) -> bool:
    if package_uri.startswith("oci://"):
        return True
    if package_uri.startswith("file://"):
        path = package_uri.removeprefix("file://")
        return bool(path) and ".." not in path.replace("\\", "/").split("/")
    path_parts = package_uri.replace("\\", "/").split("/")
    return package_uri.startswith(("./", "/")) and ".." not in path_parts


def _manifest_without_validation_token(manifest: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(manifest)
    cleaned.pop("validation_token", None)
    return cleaned
