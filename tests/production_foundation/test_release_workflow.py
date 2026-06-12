import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.release_check import run_release_check


def test_release_workflow_covers_verification_sbom_scan_provenance_and_publish() -> None:
    workflow_path = Path(".github/workflows/release.yml")
    assert workflow_path.exists(), "Missing GitHub Actions release workflow."

    workflow_text = workflow_path.read_text(encoding="utf-8")
    for snippet in [
        "uv run python scripts/release_check.py",
        "uv run python scripts/check_openapi_diff.py",
        "uv build",
        "npm run build",
        "load: true",
        "anchore/sbom-action",
        "anchore/scan-action",
        "actions/attest-build-provenance",
        "steps.build_server.outputs.digest",
        "pypa/gh-action-pypi-publish",
        "npm publish --access public",
        "gh release create",
    ]:
        assert snippet in workflow_text


def test_release_check_passes_for_current_repository_contract() -> None:
    result = run_release_check()

    assert result.errors == []
    assert result.checked == [
        "python-version",
        "sdk-js-version",
        "openapi",
        "sdk-surfaces",
        "changelog",
        "migrations",
        "docs-links",
    ]
