from pathlib import Path

import yaml


def test_ci_workflow_runs_backend_docs_and_frontend_baseline() -> None:
    workflow_path = Path(".github/workflows/ci.yml")

    assert workflow_path.exists(), "Missing GitHub Actions CI workflow."

    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    workflow_text = workflow_path.read_text(encoding="utf-8")
    jobs = workflow["jobs"]

    assert {"backend", "frontend"} <= set(jobs)
    assert "actions/setup-python" in workflow_text
    assert "actions/setup-node" in workflow_text
    assert "astral-sh/setup-uv" in workflow_text

    for command in [
        "uv run pytest -q",
        "uv run ruff check .",
        "uv run mypy apps/server tests scripts",
        "uv run python scripts/docs_quality.py",
        "uv run python scripts/compose_smoke.py",
        "uv run python scripts/helm_smoke.py",
        "npm run test",
        "npm run test:unit",
        "npm run build:e2e",
        "npm run test:e2e",
    ]:
        assert command in workflow_text


def test_playwright_config_uses_browser_installed_by_ci() -> None:
    workflow_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    config_text = Path("apps/console/playwright.config.ts").read_text(encoding="utf-8")

    assert "npx playwright install --with-deps chromium" in workflow_text
    assert 'channel: "chrome"' not in config_text
