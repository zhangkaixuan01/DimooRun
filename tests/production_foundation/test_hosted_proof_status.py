from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pytest import MonkeyPatch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.hosted_proof_status import build_hosted_proof_status  # noqa: E402


def test_hosted_proof_status_reports_matching_successful_ci_and_integration(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = _write_repo(tmp_path, include_workflow_dispatch=True)
    current_sha = "abc123"

    def fake_run(
        args: list[str],
        cwd: Path | None = None,
        check: bool | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"{current_sha}\n", stderr="")
        if args[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout="feature/proof\n", stderr="")
        if args[:3] == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["gh", "api"]:
            workflow = args[2].split("/")[-2]
            payload = {
                "workflow_runs": [
                    {
                        "id": 1001 if workflow == "ci.yml" else 1002,
                        "status": "completed",
                        "conclusion": "success",
                        "head_branch": "feature/proof",
                        "head_sha": current_sha,
                        "html_url": f"https://example.test/{workflow}",
                        "created_at": "2026-06-14T00:00:00Z",
                        "display_title": f"{workflow} green",
                    }
                ]
            }
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = build_hosted_proof_status(root=root, repo_slug="owner/repo")

    assert status.eligible_same_worktree_hosted_proof is True
    assert status.all_phases_ci_ready_to_closeout is True
    assert status.all_phases_ci_reasons == []
    assert status.workflows["ci"].workflow_dispatch is True
    assert status.workflows["integration"].latest_run is not None
    assert status.workflows["integration"].latest_run.head_sha == current_sha


def test_hosted_proof_status_flags_dirty_worktree_and_failed_ci(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = _write_repo(tmp_path, include_workflow_dispatch=False)
    current_sha = "abc123"

    def fake_run(
        args: list[str],
        cwd: Path | None = None,
        check: bool | None = None,
        capture_output: bool | None = None,
        text: bool | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout=f"{current_sha}\n", stderr="")
        if args[:4] == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return subprocess.CompletedProcess(args, 0, stdout="main\n", stderr="")
        if args[:3] == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=" M docs/readiness/scorecard.md\n",
                stderr="",
            )
        if args[:2] == ["gh", "api"]:
            workflow = args[2].split("/")[-2]
            payload = {
                "workflow_runs": [
                    {
                        "id": 2001 if workflow == "ci.yml" else 2002,
                        "status": "completed",
                        "conclusion": "failure" if workflow == "ci.yml" else "success",
                        "head_branch": "main",
                        "head_sha": current_sha,
                        "html_url": f"https://example.test/{workflow}",
                        "created_at": "2026-06-14T00:00:00Z",
                        "display_title": f"{workflow} status",
                    }
                ]
            }
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = build_hosted_proof_status(root=root, repo_slug="owner/repo")

    assert status.eligible_same_worktree_hosted_proof is False
    assert status.all_phases_ci_ready_to_closeout is False
    assert "worktree_dirty" in status.all_phases_ci_reasons
    assert "ci_workflow_dispatch_missing" in status.all_phases_ci_reasons
    assert "integration_workflow_dispatch_missing" in status.all_phases_ci_reasons
    assert "ci_latest_run_not_success" in status.all_phases_ci_reasons


def _write_repo(root: Path, *, include_workflow_dispatch: bool) -> Path:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    dispatch = "  workflow_dispatch:\n" if include_workflow_dispatch else ""
    for workflow in ("ci.yml", "integration.yml", "release.yml"):
        (workflows / workflow).write_text(
            "name: Test\n"
            "on:\n"
            f"{dispatch}"
            "  push:\n"
            "    branches:\n"
            "      - main\n",
            encoding="utf-8",
        )
    return root
