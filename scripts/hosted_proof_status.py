from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
REPO_SLUG = "zhangkaixuan01/DimooRun"
EMPTY_PROXY_ENV = {
    "ALL_PROXY": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "GIT_HTTP_PROXY": "",
    "GIT_HTTPS_PROXY": "",
}


@dataclass(frozen=True)
class WorkflowRunSummary:
    run_id: int
    status: str
    conclusion: str
    head_branch: str
    head_sha: str
    html_url: str
    created_at: str
    display_title: str


@dataclass(frozen=True)
class WorkflowProofStatus:
    workflow: str
    path: str
    workflow_dispatch: bool
    latest_run: WorkflowRunSummary | None


@dataclass(frozen=True)
class HostedProofStatus:
    repo: str
    current_sha: str
    current_branch: str
    dirty_files: list[str]
    eligible_same_worktree_hosted_proof: bool
    workflows: dict[str, WorkflowProofStatus]
    all_phases_ci_ready_to_closeout: bool
    all_phases_ci_reasons: list[str]


def build_hosted_proof_status(root: Path = ROOT, repo_slug: str = REPO_SLUG) -> HostedProofStatus:
    current_sha = _git_output(root, ["rev-parse", "HEAD"])
    current_branch = _git_output(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    dirty_files = _git_status_short(root)

    workflows = {
        "ci": _workflow_status(root, repo_slug, "ci.yml"),
        "integration": _workflow_status(root, repo_slug, "integration.yml"),
        "release": _workflow_status(root, repo_slug, "release.yml"),
    }
    ready, reasons = _all_phases_ci_closeout(current_sha, dirty_files, workflows)

    return HostedProofStatus(
        repo=repo_slug,
        current_sha=current_sha,
        current_branch=current_branch,
        dirty_files=dirty_files,
        eligible_same_worktree_hosted_proof=len(dirty_files) == 0,
        workflows=workflows,
        all_phases_ci_ready_to_closeout=ready,
        all_phases_ci_reasons=reasons,
    )


def _all_phases_ci_closeout(
    current_sha: str,
    dirty_files: list[str],
    workflows: dict[str, WorkflowProofStatus],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if dirty_files:
        reasons.append("worktree_dirty")

    for key in ("ci", "integration"):
        workflow = workflows[key]
        if not workflow.workflow_dispatch:
            reasons.append(f"{key}_workflow_dispatch_missing")
        latest_run = workflow.latest_run
        if latest_run is None:
            reasons.append(f"{key}_latest_run_missing")
            continue
        if latest_run.status != "completed":
            reasons.append(f"{key}_latest_run_not_completed")
        if latest_run.conclusion != "success":
            reasons.append(f"{key}_latest_run_not_success")
        if latest_run.head_sha != current_sha:
            reasons.append(f"{key}_latest_run_sha_mismatch")

    return (len(reasons) == 0, reasons)


def _workflow_status(root: Path, repo_slug: str, workflow_file: str) -> WorkflowProofStatus:
    workflow_path = root / ".github" / "workflows" / workflow_file
    text = workflow_path.read_text(encoding="utf-8")
    latest_run = _latest_workflow_run(repo_slug, workflow_file)
    return WorkflowProofStatus(
        workflow=workflow_file.removesuffix(".yml"),
        path=str(workflow_path.relative_to(root).as_posix()),
        workflow_dispatch="workflow_dispatch:" in text,
        latest_run=latest_run,
    )


def _latest_workflow_run(repo_slug: str, workflow_file: str) -> WorkflowRunSummary | None:
    payload = _gh_api(
        [
            "repos",
            repo_slug,
            "actions",
            "workflows",
            workflow_file,
            "runs?per_page=1",
        ]
    )
    runs = payload.get("workflow_runs", [])
    if not runs:
        return None
    run = runs[0]
    return WorkflowRunSummary(
        run_id=int(run["id"]),
        status=str(run.get("status", "")),
        conclusion=str(run.get("conclusion", "")),
        head_branch=str(run.get("head_branch", "")),
        head_sha=str(run.get("head_sha", "")),
        html_url=str(run.get("html_url", "")),
        created_at=str(run.get("created_at", "")),
        display_title=str(run.get("display_title", "")),
    )


def _git_output(root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_status_short(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]
    return lines


def _gh_api(path_parts: list[str]) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(EMPTY_PROXY_ENV)
    path = "/".join(path_parts[:5]) + "/" + path_parts[5]
    completed = subprocess.run(
        ["gh", "api", path],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def main() -> None:
    status = build_hosted_proof_status()
    print(json.dumps(asdict(status), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
