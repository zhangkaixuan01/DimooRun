import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dimoo_run.server import create_app

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
        "actions/upload-artifact@v4",
        "name: release-sbom",
        "anchore/scan-action",
        "actions/attest-build-provenance",
        "steps.build_server.outputs.digest",
        "pypa/gh-action-pypi-publish",
        "npm publish --access public",
        "gh release create",
        "release-evidence-index.txt",
        "name: release-evidence-index",
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
        "docs-consistency",
    ]


def test_release_check_flags_docs_consistency_regressions(tmp_path: Path) -> None:
    root = tmp_path
    (root / "openapi").mkdir(parents=True)
    (root / "packages" / "sdk-js" / "src").mkdir(parents=True)
    (root / "packages" / "sdk-python" / "dimoorun").mkdir(parents=True)
    (root / "docs" / "readiness").mkdir(parents=True)
    (root / "docs" / "start").mkdir(parents=True)
    (root / "examples" / "langgraph" / "support-agent").mkdir(parents=True)
    (root / "examples" / "langchain-agent" / "support-agent").mkdir(parents=True)
    (root / "examples" / "deepagents" / "support-agent").mkdir(parents=True)
    (root / "migrations" / "versions").mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        '[project]\nname = "dimoorun"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (root / "packages" / "sdk-js" / "package.json").write_text(
        '{"version":"0.1.0"}',
        encoding="utf-8",
    )
    (root / "packages" / "sdk-python" / "dimoorun" / "client.py").write_text(
        "\n".join(
            [
                "def validate_package(): ...",
                "def create_agent(): ...",
                "def create_agent_version(): ...",
                "def create_deployment(): ...",
                "def submit_deployment_task(): ...",
                "def get_run(): ...",
                "def list_run_events(): ...",
                "def replay_run(): ...",
            ]
        ),
        encoding="utf-8",
    )
    (root / "packages" / "sdk-js" / "src" / "client.ts").write_text(
        "\n".join(
            [
                "validatePackage",
                "createAgent",
                "createAgentVersion",
                "createDeployment",
                "submitDeploymentTask",
                "getRun",
                "listRunEvents",
                "replayRun",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0\n", encoding="utf-8")
    (root / "README.md").write_text(
        "\n".join(
            [
                "docs/start/quickstart.md",
                "docs/readiness/current-maturity.md",
                "docs/readiness/scorecard.md",
                "docker compose up --build",
                "uv run dimoorun run watch",
                "examples/langgraph/support-agent",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "DEMO_SCRIPT.md").write_text(
        "docker compose up --build\nuv run dimoorun run watch\n",
        encoding="utf-8",
    )
    (root / "docs" / "readiness" / "current-maturity.md").write_text(
        "Production-shaped foundation: yes.\n",
        encoding="utf-8",
    )
    (root / "docs" / "readiness" / "scorecard.md").write_text(
        "\n".join(
            [
                "Production-shaped foundation: yes.",
                "External production-grade platform: not yet.",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "start" / "quickstart.md").write_text(
        "\n".join(
            [
                "examples/langgraph/support-agent",
                "docker compose up --build",
                "uv run dimoorun run watch",
                "http://127.0.0.1:8080",
                "dev-local-key",
            ]
        ),
        encoding="utf-8",
    )
    (root / "examples" / "langgraph" / "support-agent" / "README.md").write_text(
        "\n".join(
            [
                "Production-shaped foundation: yes.",
                "External production-grade platform: not yet.",
                "examples/langgraph/support-agent",
                "docker compose up --build",
                "http://127.0.0.1:8080",
                "dev-local-key",
            ]
        ),
        encoding="utf-8",
    )
    (root / "examples" / "langchain-agent" / "support-agent" / "README.md").write_text(
        "\n".join(
            [
                "Production-shaped foundation: yes.",
                "External production-grade platform: not yet.",
                "examples/langchain-agent/support-agent",
                "docker compose up --build",
                "uv run dimoorun run watch",
                "http://127.0.0.1:8080",
                "dev-local-key",
            ]
        ),
        encoding="utf-8",
    )
    (root / "examples" / "deepagents" / "support-agent" / "README.md").write_text(
        "\n".join(
            [
                "Production-shaped foundation: yes.",
                "External production-grade platform: not yet.",
                "examples/deepagents/support-agent",
                "docker compose up --build",
                "uv run dimoorun run watch",
                "http://127.0.0.1:8080",
                "dev-local-key",
            ]
        ),
        encoding="utf-8",
    )
    (root / "migrations" / "versions" / "0001_baseline.py").write_text(
        "# baseline\n",
        encoding="utf-8",
    )
    (root / "openapi" / "dimoorun.openapi.json").write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    result = run_release_check(root)

    assert (
        "docs_consistency_maturity_missing: README.md missing "
        "Production-shaped foundation: yes."
    ) in result.errors
    assert (
        "docs_consistency_runtime_path_missing: docs/DEMO_SCRIPT.md missing "
        "http://127.0.0.1:8080"
    ) in result.errors
