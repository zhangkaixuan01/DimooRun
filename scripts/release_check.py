from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dimoo_run.server import create_app

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
OPENAPI_PATH = ROOT / "openapi" / "dimoorun.openapi.json"
SDK_JS_PACKAGE_PATH = ROOT / "packages" / "sdk-js" / "package.json"
SDK_PY_CLIENT_PATH = ROOT / "packages" / "sdk-python" / "dimoorun" / "client.py"
SDK_JS_CLIENT_PATH = ROOT / "packages" / "sdk-js" / "src" / "client.ts"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
README_PATH = ROOT / "README.md"
MIGRATIONS_DIR = ROOT / "migrations" / "versions"
REQUIRED_DOC_LINKS = [
    "docs/start/quickstart.md",
    "docs/readiness/current-maturity.md",
    "docs/readiness/scorecard.md",
]
REQUIRED_SDK_METHOD_MARKERS = [
    "validate_package",
    "create_agent",
    "create_agent_version",
    "create_deployment",
    "submit_deployment_task",
    "get_run",
    "list_run_events",
    "replay_run",
]
REQUIRED_TS_METHOD_MARKERS = [
    "validatePackage",
    "createAgent",
    "createAgentVersion",
    "createDeployment",
    "submitDeploymentTask",
    "getRun",
    "listRunEvents",
    "replayRun",
]


@dataclass(frozen=True)
class ReleaseCheckResult:
    errors: list[str]
    checked: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def run_release_check(root: Path = ROOT) -> ReleaseCheckResult:
    errors: list[str] = []
    checked: list[str] = []

    version_text = _python_version(root)
    checked.append("python-version")
    _check_js_version(root, version_text, errors)
    checked.append("sdk-js-version")
    _check_openapi_current(root, errors)
    checked.append("openapi")
    _check_sdk_surfaces(root, errors)
    checked.append("sdk-surfaces")
    _check_changelog(root, version_text, errors)
    checked.append("changelog")
    _check_migrations(root, errors)
    checked.append("migrations")
    _check_docs_links(root, errors)
    checked.append("docs-links")
    return ReleaseCheckResult(errors=errors, checked=checked)


def _python_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _check_js_version(root: Path, expected_version: str, errors: list[str]) -> None:
    package_path = root / "packages" / "sdk-js" / "package.json"
    package_json = json.loads(package_path.read_text(encoding="utf-8"))
    actual_version = str(package_json.get("version"))
    if actual_version != expected_version:
        errors.append(
            "sdk_js_version_mismatch: "
            f"pyproject.toml={expected_version} package.json={actual_version}"
        )


def _check_openapi_current(root: Path, errors: list[str]) -> None:
    if not (root / "openapi" / "dimoorun.openapi.json").exists():
        errors.append("openapi_missing: openapi/dimoorun.openapi.json is missing.")
        return
    generated = (
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    current = (root / "openapi" / "dimoorun.openapi.json").read_text(encoding="utf-8")
    if generated != current:
        errors.append("openapi_out_of_date: run `uv run python scripts/export_openapi.py`.")


def _check_sdk_surfaces(root: Path, errors: list[str]) -> None:
    python_client = (root / "packages" / "sdk-python" / "dimoorun" / "client.py").read_text(
        encoding="utf-8"
    )
    for marker in REQUIRED_SDK_METHOD_MARKERS:
        if f"def {marker}" not in python_client:
            errors.append(f"sdk_python_missing_method: {marker}")
    ts_client = (root / "packages" / "sdk-js" / "src" / "client.ts").read_text(encoding="utf-8")
    for marker in REQUIRED_TS_METHOD_MARKERS:
        if marker not in ts_client:
            errors.append(f"sdk_js_missing_method: {marker}")


def _check_changelog(root: Path, version_text: str, errors: list[str]) -> None:
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {version_text}" not in changelog:
        errors.append(f"changelog_missing_version: CHANGELOG.md must contain ## {version_text}")


def _check_migrations(root: Path, errors: list[str]) -> None:
    migration_files = sorted(
        path.name
        for path in (root / "migrations" / "versions").glob("*.py")
        if path.name != "__init__.py"
    )
    if "0001_baseline.py" not in migration_files:
        errors.append(
            "migration_baseline_missing: migrations/versions/0001_baseline.py is required."
        )


def _check_docs_links(root: Path, errors: list[str]) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    for link in REQUIRED_DOC_LINKS:
        if link not in readme:
            errors.append(f"required_docs_link_missing: README.md must reference {link}")


def main() -> None:
    result = run_release_check()
    if not result.ok:
        for error in result.errors:
            print(f"release_check failed: {error}")
        raise SystemExit(1)
    print("release_check passed: " + ", ".join(result.checked))


if __name__ == "__main__":
    main()
