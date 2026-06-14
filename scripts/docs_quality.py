from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

REQUIRED_DOCS = [
    "docs/plans/production-grade-gap-closure-2026-06-04.md",
    "docs/OPERATIONS_RUNBOOK.md",
    "docs/THREAT_MODEL.md",
    "docs/TRUST_AND_SECURITY.md",
    "docs/COMPARISONS.md",
    "docs/ROADMAP.md",
    "docs/FAQ.md",
    "docs/DEMO_SCRIPT.md",
    "docs/product/console-user-task-model.md",
    "docs/product/console-experience-acceptance.md",
    "docs/product/workflow-coverage-matrix.md",
    "docs/product/function-coverage-review.md",
    "docs/product/optimization-backlog.md",
    "docs/readiness/scorecard.md",
    "docs/README.md",
    "docs/start/product-overview.md",
    "docs/start/getting-started.md",
    "docs/reference/concepts.md",
    "docs/architecture/overview.md",
    "docs/start/quickstart.md",
    "docs/readiness/current-maturity.md",
    "docs/readiness/screenshots.md",
    "docs/readiness/compose-smoke-report.md",
    "docs/readiness/kind-smoke-report.md",
    "docs/readiness/browser-smoke-report.md",
    "docs/readiness/external-proof-matrix.md",
    "docs/readiness/all-phases-ci-proof.md",
    "docs/readiness/release-proof-report.md",
    "docs/readiness/phase-0m-evidence.md",
    "docs/readiness/phase-0n-evidence.md",
    "docs/readiness/phase-0o-evidence.md",
    "docs/readiness/walkthroughs/2026-06-guided-activation-and-promotion.md",
    "docs/readiness/walkthroughs/2026-06-failed-run-triage-and-approval.md",
    "docs/readiness/walkthroughs/2026-06-incident-recovery.md",
    "docs/architecture/adrs/0001-runtime-control-plane.md",
    "examples/langgraph/support-agent/README.md",
    "examples/langchain-agent/support-agent/README.md",
    "examples/deepagents/support-agent/README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
]

REQUIRED_REPO_FILES = [
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
]

REQUIRED_SECTIONS = {
    "README.md": [
        "# DimooRun",
        "## Why Teams Use DimooRun",
        "## First 15 Minutes",
        "## Architecture Signal",
        "## Screenshots",
        "## Supported Modes",
        "## Current Maturity",
        "## What DimooRun Is Not",
    ],
    "docs/README.md": [
        "# DimooRun Documentation",
        "## Start Here",
        "## Evaluation Path",
        "## Product",
        "## API And SDK",
        "## Readiness",
        "## Trust And Operations",
        "## Examples",
        "## Community",
        "## Known Gaps",
        "## Directory Map",
    ],
    "docs/OPERATIONS_RUNBOOK.md": [
        "# Operations Runbook",
        "## Scope",
        "## Runtime Health Checks",
        "## Run Failure Triage",
        "## Backup And Restore",
    ],
    "docs/THREAT_MODEL.md": [
        "# Threat Model",
        "## Scope",
        "## Trust Boundaries",
        "## Threats By Surface",
        "## Residual Risks",
    ],
    "docs/TRUST_AND_SECURITY.md": [
        "# Trust And Security",
        "## Security Posture",
        "## Security Reporting",
        "## Dependency And Supply Chain Checks",
        "## Secret Handling Model",
        "## Production Safety Defaults",
    ],
    "docs/COMPARISONS.md": [
        "# Comparisons",
        "## Versus A Plain LangGraph App",
        "## Versus LangGraph Platform-Style Compatibility",
        "## Versus Generic Workflow Engines",
        "## Versus Model Gateways",
    ],
    "docs/ROADMAP.md": [
        "# Roadmap",
        "## Principles",
        "## Now",
        "## Next",
        "## Later",
        "## Boundaries",
    ],
    "docs/FAQ.md": [
        "# FAQ",
        "## What Is DimooRun?",
        "## Is It Ready For External Production Use?",
        "## How Should I Contribute?",
    ],
    "docs/DEMO_SCRIPT.md": [
        "# Demo Script",
        "## Prerequisites",
        "## Agent Publish",
        "## Deployment Promote",
        "## Run Inspect",
        "## Replay",
        "## Policy Approval",
        "## Gateway Route Test",
        "## Incident Triage",
        "## Cost Drilldown",
    ],
    "docs/start/product-overview.md": [
        "# Product Overview",
        "## What DimooRun Is",
        "## Where It Fits",
        "## Core Workflows",
        "## Non-Goals",
    ],
    "docs/start/getting-started.md": [
        "# Getting Started",
        "## Prerequisites",
        "## First Runtime Path",
        "## Evaluation Checkpoints",
    ],
    "docs/reference/concepts.md": [
        "# Concepts",
        "## Resource Model",
        "## Control Plane And Runtime Plane",
        "## Runtime Evidence",
        "## Compatibility Boundary",
    ],
    "docs/architecture/overview.md": [
        "# Architecture",
        "## Control Plane",
        "## Runtime Plane",
        "## Agent Plane",
        "## Worker Loop",
        "## Governance Decision Path",
        "## Compatibility Path",
        "## Observability Path",
    ],
    "docs/start/quickstart.md": ["# Quickstart", "## Working Directory", "## Verify The Run"],
    "docs/readiness/current-maturity.md": [
        "# Current Maturity",
        "## Current Status",
        "## What You Can Evaluate Today",
        "## Known Gaps",
    ],
    "docs/readiness/screenshots.md": [
        "# Screenshots",
        "## Required Screenshots",
        "## Placeholder Gallery",
        "## Current State",
    ],
    "docs/readiness/compose-smoke-report.md": [
        "# Compose Smoke Report",
        "## Command",
        "## Result",
        "## Evidence",
        "## Next Action",
        "## Hosted CI Backfill Template",
        "## Scorecard Rows To Update",
    ],
    "docs/readiness/kind-smoke-report.md": [
        "# KinD Smoke Report",
        "## Command",
        "## Result",
        "## Evidence",
        "## Next Action",
        "## Hosted CI Backfill Template",
        "## Scorecard Rows To Update",
    ],
    "docs/readiness/browser-smoke-report.md": [
        "# Browser Smoke Report",
        "## Command",
        "## Result",
        "## Evidence",
        "## Next Action",
    ],
    "docs/readiness/external-proof-matrix.md": [
        "# Outstanding External Proof Matrix",
        "## How To Use",
        "## Open External Proof Items",
        "## Completion Transaction",
        "## Backfill Rule",
    ],
    "docs/readiness/release-proof-report.md": [
        "# Release Proof Report",
        "## Workflow Contract",
        "## Current State",
        "## Hosted CI Backfill Template",
        "## Scorecard Rows To Update",
        "## Closure Verdict",
    ],
    "docs/readiness/all-phases-ci-proof.md": [
        "# All-Phases CI Proof",
        "## Workflow Contract",
        "## Current State",
        "## Hosted CI Backfill Template",
        "## Scorecard Rows To Update",
        "## Closure Verdict",
    ],
    "docs/readiness/phase-0m-evidence.md": [
        "# Phase 0M Evidence Checklist",
        "## What Is Already Proven",
        "## Hosted CI Gap",
        "## Hosted CI Backfill Template",
        "## Latest Local Result",
        "## Local Operator Notes",
        "## Scorecard Rows To Update",
        "## Closure Verdict",
    ],
    "docs/readiness/phase-0n-evidence.md": [
        "# Phase 0N Evidence Checklist",
        "## What Is Already Proven",
        "## Hosted CI Gap",
        "## Hosted CI Backfill Template",
        "## Latest Local Result",
        "## Local Operator Notes",
        "## Scorecard Rows To Update",
        "## Closure Verdict",
    ],
    "docs/readiness/phase-0o-evidence.md": [
        "# Phase 0O Evidence Checklist",
        "## What Is Already Proven",
        "## Hosted CI Gap",
        "## Hosted CI Backfill Template",
        "## Latest Local Result",
        "## Local Operator Notes",
        "## Scorecard Rows To Update",
        "## Closure Verdict",
    ],
    "docs/readiness/scorecard.md": [
        "# Production Readiness Scorecard",
        "## Milestone Status",
        "## Early Phase Status",
        "## Milestone A Exit Criteria",
        "## Milestone B Exit Criteria",
        "## Milestone C Exit Criteria",
        "## Milestone D Exit Criteria",
        "## Definition Of Done Audit",
        "## Hosted Evidence Backfill",
        "## Claim Guardrails",
    ],
    "docs/readiness/walkthroughs/2026-06-guided-activation-and-promotion.md": [
        "# Walkthrough: Guided Activation And Deployment Promotion",
        "## Roles",
        "## Workflow Scope",
        "## Preconditions",
        "## Walkthrough",
        "## Friction Log",
        "## Follow-Up Backlog Items",
    ],
    "docs/readiness/walkthroughs/2026-06-failed-run-triage-and-approval.md": [
        "# Walkthrough: Failed-Run Triage And Approval Decision",
        "## Roles",
        "## Workflow Scope",
        "## Preconditions",
        "## Walkthrough",
        "## Friction Log",
        "## Follow-Up Backlog Items",
    ],
    "docs/readiness/walkthroughs/2026-06-incident-recovery.md": [
        "# Walkthrough: Incident Recovery",
        "## Roles",
        "## Workflow Scope",
        "## Preconditions",
        "## Walkthrough",
        "## Friction Log",
        "## Follow-Up Backlog Items",
    ],
    "docs/architecture/adrs/0001-runtime-control-plane.md": [
        "# ADR 0001: Runtime Control Plane",
        "## Decision",
        "## Consequences",
    ],
    "examples/langgraph/support-agent/README.md": [
        "# LangGraph Support Agent Example",
        "## Manifest",
        "## Expected Commands",
        "## Expected Console Result",
        "## Troubleshooting",
        "## Production Caveats",
    ],
    "examples/langchain-agent/support-agent/README.md": [
        "# LangChain Agent Support Example",
        "## Manifest",
        "## Expected Commands",
        "## Expected Console Result",
        "## Troubleshooting",
        "## Production Caveats",
    ],
    "examples/deepagents/support-agent/README.md": [
        "# DeepAgents Support Example",
        "## Manifest",
        "## Expected Commands",
        "## Expected Console Result",
        "## Troubleshooting",
        "## Production Caveats",
    ],
    "CONTRIBUTING.md": [
        "# Contributing",
        "## Development Setup",
        "## Coding Standards",
        "## Test Expectations",
        "## Pull Requests",
    ],
    "SECURITY.md": [
        "# Security Policy",
        "## Reporting A Vulnerability",
        "## Supported Scope",
        "## Response Expectations",
    ],
    "CHANGELOG.md": [
        "# Changelog",
        "## Unreleased",
        "## 0.1.0",
    ],
}

REQUIRED_MILESTONES = [
    "Milestone A: Internal Alpha",
    "Milestone B: Production Beta",
    "Milestone C: External GA",
    "Milestone D: Competitive Excellence",
]

REQUIRED_MILESTONE_EXIT_SECTIONS = [
    "## Milestone A Exit Criteria",
    "## Milestone B Exit Criteria",
    "## Milestone C Exit Criteria",
    "## Milestone D Exit Criteria",
]

REQUIRED_DOD_AUDIT_ITEMS = [
    "All phases have passing tests in CI.",
    (
        "Every core workflow maps to a named user role, job, decision, risk, "
        "success feedback, and failure recovery path."
    ),
    (
        "Generic CRUD coverage is no longer counted as complete unless a workflow "
        "has domain validation, action availability, audit behavior, and browser "
        "coverage."
    ),
    (
        "Product function coverage review exists and is kept current for all major "
        "product areas, including lifecycle, runtime, governance, exposure, "
        "compatibility, operations, identity, quality, cost, assets, settings, "
        "developer experience, and soft power."
    ),
    "Docker Compose smoke passes from a clean checkout.",
    "Kubernetes smoke passes in an ephemeral cluster.",
    "Release workflow builds, scans, signs or attests, and publishes artifacts.",
]

REQUIRED_PHASES = [
    "Phase -3: User Task And Experience Baseline",
    "Phase -2: Product Workflow Spec Reconciliation",
    "Phase -1A: Frontend Test Harness Baseline",
    "Phase -1B: Frontend State Architecture Baseline",
    "Phase -1C: Console Aggregate And Permission API Contract",
    "Phase 1: Production Truth Baseline",
    "Phase 12A: Product Narrative Baseline",
    "Phase 12B: Product Trust Assets, Examples, Demo, And Community",
]

ALLOWED_STATUSES = {"complete", "partial", "missing", "blocked"}
SHELL_FENCES = {"bash", "sh", "shell", "powershell", "ps1", "pwsh"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
UNSUPPORTED_MATURITY_PHRASES = [
    "production-ready",
    "fully production ready",
    "perfect production-grade",
]
STALE_MATURITY_PHRASES = [
    "belong to the next phase",
    "next product-doc phase is trust assets",
]
CANONICAL_MATURITY_LINES = [
    "Production-shaped foundation: yes.",
    "External production-grade platform: not yet.",
]
CONSISTENT_RUNTIME_PATH_DOCS = {
    "README.md": [
        "examples/langgraph/support-agent",
        "docker compose up --build",
        "uv run dimoorun run watch",
    ],
    "docs/start/quickstart.md": [
        "examples/langgraph/support-agent",
        "docker compose up --build",
        "uv run dimoorun run watch",
        "http://127.0.0.1:8080",
        "dev-local-key",
    ],
    "examples/langgraph/support-agent/README.md": [
        "examples/langgraph/support-agent",
        "docker compose up --build",
        "uv run dimoorun run watch",
        "http://127.0.0.1:8080",
        "dev-local-key",
    ],
    "docs/DEMO_SCRIPT.md": [
        "docker compose up --build",
        "uv run dimoorun run watch",
        "http://127.0.0.1:8080",
        "dev-local-key",
        "examples/langgraph/support-agent",
    ],
    "examples/langchain-agent/support-agent/README.md": [
        "examples/langchain-agent/support-agent",
        "docker compose up --build",
        "uv run dimoorun run watch",
        "http://127.0.0.1:8080",
        "dev-local-key",
    ],
    "examples/deepagents/support-agent/README.md": [
        "examples/deepagents/support-agent",
        "docker compose up --build",
        "uv run dimoorun run watch",
        "http://127.0.0.1:8080",
        "dev-local-key",
    ],
}

HOSTED_PROOF_CONTRACTS: dict[str, HostedProofContract] = {
    "docs/readiness/phase-0m-evidence.md": {
        "matrix_label": "Hosted browser proof for Phase 0M",
        "scorecard_label": "Hosted browser matrix closeout for 0M",
        "artifacts": [
            "`console-playwright-0m-report`",
            "`console-playwright-evidence-index`",
        ],
        "scorecard_rows": [
            (
                "`Cost and budget workflows explain usage by agent, deployment, run, "
                "provider, tenant, project, and environment, with anomaly and budget "
                "guardrails.`"
            ),
            "`Browser E2E tests cover core Console workflows.`",
            "`Milestone C: External GA`",
        ],
    },
    "docs/readiness/phase-0n-evidence.md": {
        "matrix_label": "Hosted browser proof for Phase 0N",
        "scorecard_label": "Hosted browser matrix closeout for 0N",
        "artifacts": [
            "`console-playwright-0n-report`",
            "`console-playwright-evidence-index`",
        ],
        "scorecard_rows": [
            (
                "`Scheduled Run and Batch Run are first-class runtime task shapes with "
                "validation, state machines, cancellation, replay, audit, and browser "
                "coverage.`"
            ),
            "`Browser E2E tests cover core Console workflows.`",
            "`Milestone C: External GA`",
        ],
    },
    "docs/readiness/phase-0o-evidence.md": {
        "matrix_label": "Hosted browser proof for Phase 0O",
        "scorecard_label": "Hosted browser matrix closeout for 0O",
        "artifacts": [
            "`console-playwright-0o-report`",
            "`console-playwright-evidence-index`",
        ],
        "scorecard_rows": [
            (
                "`Catalog, Prompt, Config, and Template assets have version lifecycle, "
                "validation, dependency visibility, approval, rollback, and used-by "
                "impact.`"
            ),
            "`Browser E2E tests cover core Console workflows.`",
            "`Milestone C: External GA`",
        ],
    },
    "docs/readiness/compose-smoke-report.md": {
        "matrix_label": "Hosted Compose smoke proof",
        "scorecard_label": "Hosted Compose smoke closeout",
        "artifacts": [
            "`compose-runtime-smoke`",
            "`compose-runtime-smoke-index`",
        ],
        "scorecard_rows": [
            "`Phase 1: Production Truth Baseline`",
            "`Phase 10: Deployment And Operations Hardening`",
            "`Docker Compose smoke passes from a clean checkout.`",
            "`Milestone C: External GA`",
        ],
    },
    "docs/readiness/kind-smoke-report.md": {
        "matrix_label": "Hosted KinD smoke proof",
        "scorecard_label": "Hosted KinD smoke closeout",
        "artifacts": [
            "`kind-smoke`",
            "`kind-smoke-index`",
        ],
        "scorecard_rows": [
            "`Phase 10: Deployment And Operations Hardening`",
            "`Kubernetes smoke passes in an ephemeral cluster.`",
            "`Milestone C: External GA`",
        ],
    },
    "docs/readiness/release-proof-report.md": {
        "matrix_label": "Hosted release proof",
        "scorecard_label": "Hosted release closeout",
        "artifacts": [
            "`release-evidence-index`",
            "`release-sbom`",
        ],
        "scorecard_rows": [
            "`Phase 11: SDK, CLI, And Release Engineering`",
            "`Milestone C: External GA`",
            "`Release workflow builds, scans, signs or attests, and publishes artifacts.`",
            (
                "`SDK, CLI, README, quickstart, examples, trust docs, and release "
                "workflow are coherent and versioned.`"
            ),
        ],
    },
    "docs/readiness/all-phases-ci-proof.md": {
        "matrix_label": "Hosted all-phases CI proof",
        "scorecard_label": "Hosted all-phases CI closeout",
        "artifacts": [
            "`console-playwright-evidence-index`",
            "`compose-runtime-smoke-index`",
            "`kind-smoke-index`",
        ],
        "scorecard_rows": [
            "`All phases have passing tests in CI.`",
            "`Milestone A: Internal Alpha`",
            "`Milestone B: Production Beta`",
            "`Milestone C: External GA`",
        ],
    },
}


@dataclass(frozen=True)
class DocsQualityResult:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class HostedProofContract(TypedDict):
    matrix_label: str
    scorecard_label: str
    artifacts: list[str]
    scorecard_rows: list[str]


def validate_docs_quality(root: Path) -> DocsQualityResult:
    errors: list[str] = []

    for relative_path in REQUIRED_DOCS:
        path = root / relative_path
        if not path.exists():
            errors.append(f"Missing required documentation file: {relative_path}")
            continue
        if relative_path in REQUIRED_SECTIONS:
            text = path.read_text(encoding="utf-8")
            for section in REQUIRED_SECTIONS[relative_path]:
                if section not in text:
                    errors.append(f"{relative_path} missing required section: {section}")

    for relative_path in REQUIRED_REPO_FILES:
        path = root / relative_path
        if not path.exists():
            errors.append(f"Missing required repository file: {relative_path}")

    scorecard_path = root / "docs/readiness/scorecard.md"
    if scorecard_path.exists():
        scorecard = scorecard_path.read_text(encoding="utf-8")
        errors.extend(_validate_scorecard(scorecard))

    readme_path = root / "README.md"
    if readme_path.exists():
        errors.extend(_validate_unsupported_claims(readme_path, root))

    for relative_path in REQUIRED_SECTIONS:
        doc_path = root / relative_path
        if doc_path.exists() and relative_path != "README.md":
            errors.extend(_validate_unsupported_claims(doc_path, root))

    errors.extend(_validate_internal_links(root))
    errors.extend(_validate_image_refs(root))
    errors.extend(_validate_command_blocks(root))
    errors.extend(_validate_comparison_evidence(root))
    errors.extend(_validate_security_links(root))
    errors.extend(_validate_changelog_entries(root))
    errors.extend(_validate_demo_prerequisites(root))
    errors.extend(_validate_stale_maturity_wording(root))
    errors.extend(_validate_walkthroughs(root))
    errors.extend(_validate_maturity_consistency(root))
    errors.extend(_validate_runtime_path_consistency(root))
    errors.extend(_validate_external_proof_matrix(root))
    errors.extend(_validate_hosted_proof_consistency(root))

    return DocsQualityResult(errors=errors)


def _validate_scorecard(scorecard: str) -> list[str]:
    errors: list[str] = []

    if "# Production Readiness Scorecard" not in scorecard:
        errors.append("Readiness scorecard must start with '# Production Readiness Scorecard'.")

    for milestone in REQUIRED_MILESTONES:
        if milestone not in scorecard:
            errors.append(f"Readiness scorecard missing {milestone}.")

    for section in REQUIRED_MILESTONE_EXIT_SECTIONS:
        if section not in scorecard:
            errors.append(f"Readiness scorecard missing exit criteria section: {section}")

    if "## Definition Of Done Audit" not in scorecard:
        errors.append("Readiness scorecard missing section: ## Definition Of Done Audit")

    for item in REQUIRED_DOD_AUDIT_ITEMS:
        if item not in scorecard:
            errors.append(f"Readiness scorecard missing Definition of Done audit item: {item}")

    for phase in REQUIRED_PHASES:
        if phase not in scorecard:
            errors.append(f"Readiness scorecard missing {phase}.")

    status_rows = _extract_status_rows(scorecard)
    for item, status in status_rows:
        if status not in ALLOWED_STATUSES:
            errors.append(f"Invalid readiness status for {item}: {status}")

    if not any(item == "Milestone A: Internal Alpha" for item, _ in status_rows):
        errors.append("Readiness scorecard must include a status row for Milestone A.")

    if not any(item == "Phase -2: Product Workflow Spec Reconciliation" for item, _ in status_rows):
        errors.append("Readiness scorecard must include a status row for Phase -2.")

    return errors


def _extract_status_rows(markdown: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in markdown.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip(" `").lower() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in {"item", "phase", "milestone", "---"}:
            continue
        status = cells[1]
        if status in ALLOWED_STATUSES or any(status == candidate for candidate in ALLOWED_STATUSES):
            item = line.strip().strip("|").split("|")[0].strip(" `")
            rows.append((item, status))
    return rows


def _validate_internal_links(root: Path) -> list[str]:
    errors: list[str] = []
    for markdown_path in _markdown_files(root):
        text = markdown_path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or _is_external_or_special_link(target):
                continue
            target_path = (markdown_path.parent / target).resolve()
            try:
                target_path.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"Internal link in {_relative(markdown_path, root)} points outside repo: "
                    f"{target}"
                )
                continue
            if not target_path.exists():
                errors.append(f"Broken internal link in {_relative(markdown_path, root)}: {target}")
    return errors


def _validate_command_blocks(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in REQUIRED_SECTIONS:
        markdown_path = root / relative_path
        if not markdown_path.exists():
            continue
        lines = markdown_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip().lower()
            if not stripped.startswith("```"):
                continue
            language = stripped.removeprefix("```").strip()
            if language not in SHELL_FENCES:
                continue
            context = "\n".join(lines[max(0, index - 4) : index]).lower()
            if "working directory:" not in context:
                errors.append(
                    f"Command block in {_relative(markdown_path, root)} must declare a working "
                    "directory nearby."
                )
    return errors


def _validate_image_refs(root: Path) -> list[str]:
    errors: list[str] = []
    for markdown_path in _markdown_files(root):
        text = markdown_path.read_text(encoding="utf-8")
        for match in MARKDOWN_IMAGE.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or _is_external_or_special_link(target):
                continue
            target_path = (markdown_path.parent / target).resolve()
            try:
                target_path.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    f"Image reference in {_relative(markdown_path, root)} points outside repo: "
                    f"{target}"
                )
                continue
            if not target_path.exists():
                errors.append(
                    "Broken image reference in "
                    f"{_relative(markdown_path, root)}: {target}"
                )
    return errors


def _validate_unsupported_claims(markdown_path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        normalized = line.lower()
        for phrase in UNSUPPORTED_MATURITY_PHRASES:
            if phrase not in normalized:
                continue
            if _line_is_negated_claim(normalized, phrase):
                continue
            errors.append(
                f"{_relative(markdown_path, root)} contains unsupported maturity claim: {phrase}"
            )
    return errors


def _line_is_negated_claim(line: str, phrase: str) -> bool:
    prefix = line.split(phrase, 1)[0]
    negation_markers = (
        "not ",
        "do not ",
        "must not ",
        "should not ",
        "is not ",
        "are not ",
        "isn't ",
        "aren't ",
        "without ",
    )
    return any(marker in prefix for marker in negation_markers)


def _markdown_files(root: Path) -> list[Path]:
    files = sorted((root / "docs").rglob("*.md"))
    files.extend(
        [
            root / "README.md",
            root / "CONTRIBUTING.md",
            root / "SECURITY.md",
            root / "CHANGELOG.md",
            root / "examples" / "langgraph" / "support-agent" / "README.md",
            root / "examples" / "langchain-agent" / "support-agent" / "README.md",
            root / "examples" / "deepagents" / "support-agent" / "README.md",
        ]
    )
    return [path for path in files if path.exists()]


def _is_external_or_special_link(target: str) -> bool:
    return (
        target.startswith("http://")
        or target.startswith("https://")
        or target.startswith("mailto:")
        or target.startswith("file:")
        or target.startswith("#")
    )


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _validate_comparison_evidence(root: Path) -> list[str]:
    path = root / "docs/COMPARISONS.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if text.count("### Evidence In Repository") < 4:
        return ["docs/COMPARISONS.md must provide repository evidence for each comparison."]
    return []


def _validate_security_links(root: Path) -> list[str]:
    path = root / "docs/TRUST_AND_SECURITY.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for target in ("../SECURITY.md", "THREAT_MODEL.md", "OPERATIONS_RUNBOOK.md"):
        if f"({target})" not in text:
            errors.append(f"docs/TRUST_AND_SECURITY.md missing required link: {target}")
    return errors


def _validate_changelog_entries(root: Path) -> list[str]:
    path = root / "CHANGELOG.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if "## Unreleased" not in text:
        return ["CHANGELOG.md must contain an Unreleased section."]
    if "Phase 12B" not in text and "trust and security docs" not in text.lower():
        return ["CHANGELOG.md must mention the Phase 12B trust/examples/community changes."]
    return []


def _validate_demo_prerequisites(root: Path) -> list[str]:
    path = root / "docs/DEMO_SCRIPT.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for phrase in ("## Prerequisites", "docker compose up --build", "uv run dimoorun run watch"):
        if phrase not in text:
            errors.append(f"docs/DEMO_SCRIPT.md missing demo prerequisite or command: {phrase}")
    return errors


def _validate_stale_maturity_wording(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in ("docs/README.md", "docs/readiness/current-maturity.md"):
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in STALE_MATURITY_PHRASES:
            if phrase in text:
                errors.append(f"{relative_path} contains stale maturity wording: {phrase}")
    return errors


def _validate_walkthroughs(root: Path) -> list[str]:
    walkthrough_dir = root / "docs" / "readiness" / "walkthroughs"
    if not walkthrough_dir.exists():
        return ["Missing walkthrough directory: docs/readiness/walkthroughs"]
    walkthroughs = sorted(walkthrough_dir.glob("*.md"))
    if len(walkthroughs) < 3:
        return [
            "docs/readiness/walkthroughs must contain at least three walkthrough records."
        ]
    errors: list[str] = []
    required_phrases = [
        "guided activation",
        "deployment promotion",
        "failed-run triage",
        "approval decision",
        "incident recovery",
        "friction log",
        "follow-up backlog items",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in walkthroughs)
    for phrase in required_phrases:
        if phrase not in combined:
            errors.append(
                "Walkthrough evidence is missing required coverage phrase: "
                f"{phrase}"
            )
    return errors


def _validate_maturity_consistency(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in (
        "README.md",
        "docs/DEMO_SCRIPT.md",
        "docs/readiness/current-maturity.md",
        "docs/readiness/scorecard.md",
        "examples/langgraph/support-agent/README.md",
        "examples/langchain-agent/support-agent/README.md",
        "examples/deepagents/support-agent/README.md",
    ):
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for line in CANONICAL_MATURITY_LINES:
            if line not in text:
                errors.append(
                    f"{relative_path} missing canonical maturity line: {line}"
                )
    return errors


def _validate_runtime_path_consistency(root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, required_phrases in CONSISTENT_RUNTIME_PATH_DOCS.items():
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            if phrase not in text:
                errors.append(
                    f"{relative_path} missing required runtime path phrase: {phrase}"
                )
    return errors


def _validate_external_proof_matrix(root: Path) -> list[str]:
    path = root / "docs/readiness/external-proof-matrix.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    required_phrases = [
        "Required scorecard row updates",
        "## Completion Transaction",
        "Update every scorecard row named in `Required scorecard row updates`.",
        "## Hosted Evidence Backfill",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            errors.append(
                "docs/readiness/external-proof-matrix.md missing required external "
                f"proof phrase: {phrase}"
            )
    return errors


def _validate_hosted_proof_consistency(root: Path) -> list[str]:
    errors: list[str] = []
    matrix_path = root / "docs/readiness/external-proof-matrix.md"
    scorecard_path = root / "docs/readiness/scorecard.md"
    matrix = matrix_path.read_text(encoding="utf-8") if matrix_path.exists() else ""
    scorecard = scorecard_path.read_text(encoding="utf-8") if scorecard_path.exists() else ""
    for relative_path, contract in HOSTED_PROOF_CONTRACTS.items():
        path = root / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "## Scorecard Rows To Update" not in text:
            errors.append(f"{relative_path} missing required section: ## Scorecard Rows To Update")
        if contract["matrix_label"] not in matrix:
            errors.append(
                "docs/readiness/external-proof-matrix.md missing hosted proof row: "
                f"{contract['matrix_label']}"
            )
        if contract["scorecard_label"] not in scorecard:
            errors.append(
                "docs/readiness/scorecard.md missing hosted evidence row: "
                f"{contract['scorecard_label']}"
            )
        if relative_path not in matrix:
            errors.append(
                "docs/readiness/external-proof-matrix.md missing backfill document link: "
                f"{relative_path}"
            )
        if relative_path not in scorecard:
            errors.append(
                "docs/readiness/scorecard.md missing hosted evidence backfill link: "
                f"{relative_path}"
            )
        for artifact in contract["artifacts"]:
            if artifact not in text:
                errors.append(f"{relative_path} missing hosted artifact reference: {artifact}")
            if artifact not in matrix:
                errors.append(
                    "docs/readiness/external-proof-matrix.md missing hosted artifact reference: "
                    f"{artifact}"
                )
            if artifact not in scorecard:
                errors.append(
                    "docs/readiness/scorecard.md missing hosted artifact reference: "
                    f"{artifact}"
                )
        for row in contract["scorecard_rows"]:
            if row not in text:
                errors.append(
                    f"{relative_path} missing scorecard row update reference: {row}"
                )
    return errors
