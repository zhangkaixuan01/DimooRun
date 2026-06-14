import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.docs_quality import validate_docs_quality  # noqa: E402

PHASE_12A_DOCS = {
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


def test_readiness_scorecard_has_milestone_and_phase_statuses() -> None:
    result = validate_docs_quality(ROOT)

    assert result.errors == []


def test_phase_12a_product_narrative_docs_exist_with_required_sections() -> None:
    for relative_path, required_sections in PHASE_12A_DOCS.items():
        path = ROOT / relative_path
        assert path.exists(), f"Missing Phase 12A doc: {relative_path}"
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            assert section in text, f"{relative_path} missing section: {section}"


def test_walkthrough_docs_record_three_user_role_walkthroughs_with_friction_logs() -> None:
    walkthrough_dir = ROOT / "docs/readiness/walkthroughs"
    walkthroughs = sorted(walkthrough_dir.glob("*.md"))

    assert len(walkthroughs) >= 3
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in walkthroughs)
    for phrase in [
        "guided activation",
        "deployment promotion",
        "failed-run triage",
        "approval decision",
        "incident recovery",
        "friction log",
        "follow-up backlog items",
    ]:
        assert phrase in combined


def test_scorecard_records_all_milestone_exit_sections() -> None:
    scorecard = (ROOT / "docs/readiness/scorecard.md").read_text(encoding="utf-8")

    for section in [
        "## Milestone A Exit Criteria",
        "## Milestone B Exit Criteria",
        "## Milestone C Exit Criteria",
        "## Milestone D Exit Criteria",
        "## Definition Of Done Audit",
    ]:
        assert section in scorecard


def test_scorecard_records_definition_of_done_audit_items() -> None:
    scorecard = (ROOT / "docs/readiness/scorecard.md").read_text(encoding="utf-8")

    for item in [
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
    ]:
        assert item in scorecard


def test_docs_quality_requires_canonical_maturity_lines_and_runtime_path_markers(
    tmp_path: Path,
) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "README.md").write_text(
        "# DimooRun\n\n"
        "## Why Teams Use DimooRun\n\n"
        "## First 15 Minutes\n\n"
        "docker compose up --build\n\n"
        "## Architecture Signal\n\n"
        "## Screenshots\n\n"
        "## Supported Modes\n\n"
        "## Current Maturity\n\n"
        "## What DimooRun Is Not\n",
        encoding="utf-8",
    )
    (root / "docs/readiness/current-maturity.md").write_text(
        "# Current Maturity\n\n"
        "## Current Status\n\n"
        "## What You Can Evaluate Today\n\n"
        "## Known Gaps\n",
        encoding="utf-8",
    )
    (root / "examples/langgraph/support-agent/README.md").write_text(
        "# LangGraph Support Agent Example\n\n"
        "## Manifest\n\n"
        "## Expected Commands\n\n"
        "docker compose up --build\n\n"
        "## Expected Console Result\n\n"
        "## Troubleshooting\n\n"
        "## Production Caveats\n",
        encoding="utf-8",
    )
    (root / "docs/DEMO_SCRIPT.md").write_text(
        "# Demo Script\n\n"
        "## Prerequisites\n\n"
        "docker compose up --build\n\n"
        "## Agent Publish\n\n"
        "## Deployment Promote\n\n"
        "## Run Inspect\n\n"
        "uv run dimoorun run watch\n\n"
        "## Replay\n\n"
        "## Policy Approval\n\n"
        "## Gateway Route Test\n\n"
        "## Incident Triage\n\n"
        "## Cost Drilldown\n",
        encoding="utf-8",
    )
    (root / "examples/langchain-agent/support-agent/README.md").write_text(
        "# LangChain Agent Support Example\n\n"
        "## Manifest\n\n"
        "## Expected Commands\n\n"
        "docker compose up --build\n\n"
        "## Expected Console Result\n\n"
        "## Troubleshooting\n\n"
        "## Production Caveats\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "README.md missing canonical maturity line: Production-shaped foundation: yes."
        in result.errors
    )
    assert (
        "docs/readiness/current-maturity.md missing canonical maturity line: "
        "External production-grade platform: not yet."
        in result.errors
    )
    assert (
        "examples/langgraph/support-agent/README.md missing required runtime path phrase: "
        "uv run dimoorun run watch"
        in result.errors
    )
    assert (
        "docs/DEMO_SCRIPT.md missing canonical maturity line: Production-shaped "
        "foundation: yes."
        in result.errors
    )
    assert (
        "examples/langchain-agent/support-agent/README.md missing required runtime path "
        "phrase: dev-local-key"
        in result.errors
    )


def test_docs_quality_flags_broken_internal_links(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/README.md").write_text(
        "# DimooRun Documentation\n\n"
        "## Start Here\n\n"
        "[Missing](MISSING.md)\n\n"
        "## Reference\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert "Broken internal link in docs/README.md: MISSING.md" in result.errors


def test_docs_quality_flags_broken_image_refs(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "README.md").write_text(
        "# DimooRun\n\n"
        "## Why Teams Use DimooRun\n\n"
        "## First 15 Minutes\n\n"
        "## Architecture Signal\n\n"
        "## Screenshots\n\n"
        "![Missing](docs/readiness/placeholders/missing.svg)\n\n"
        "## Supported Modes\n\n"
        "## Current Maturity\n\n"
        "## What DimooRun Is Not\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "Broken image reference in README.md: docs/readiness/placeholders/missing.svg"
        in result.errors
    )


def test_docs_quality_requires_working_directory_before_command_blocks(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/start/quickstart.md").write_text(
        "# Quickstart\n\n"
        "## Working Directory\n\n"
        "## Verify The Run\n\n"
        "```bash\n"
        "docker compose up --build\n"
        "```\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "Command block in docs/start/quickstart.md must declare a working directory nearby."
        in result.errors
    )


def test_docs_quality_rejects_unsupported_maturity_claims(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "README.md").write_text(
        "# DimooRun\n\n"
        "## Why Teams Use DimooRun\n\n"
        "## First 15 Minutes\n\n"
        "## Architecture Signal\n\n"
        "## Screenshots\n\n"
        "## Supported Modes\n\n"
        "## Current Maturity\n\n"
        "This is production-ready.\n\n"
        "## What DimooRun Is Not\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert "README.md contains unsupported maturity claim: production-ready" in result.errors


def test_docs_quality_requires_comparison_evidence_and_security_links(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/COMPARISONS.md").write_text(
        "# Comparisons\n\n"
        "## Versus A Plain LangGraph App\n\n"
        "## Versus LangGraph Platform-Style Compatibility\n\n"
        "## Versus Generic Workflow Engines\n\n"
        "## Versus Model Gateways\n",
        encoding="utf-8",
    )
    (root / "docs/TRUST_AND_SECURITY.md").write_text(
        "# Trust And Security\n\n"
        "## Security Posture\n\n"
        "## Security Reporting\n\n"
        "## Dependency And Supply Chain Checks\n\n"
        "## Secret Handling Model\n\n"
        "## Production Safety Defaults\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/COMPARISONS.md must provide repository evidence for each comparison."
        in result.errors
    )
    assert "docs/TRUST_AND_SECURITY.md missing required link: ../SECURITY.md" in result.errors


def test_docs_quality_requires_demo_prerequisites_and_unreleased_changelog(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/DEMO_SCRIPT.md").write_text(
        "# Demo Script\n\n"
        "## Prerequisites\n\n"
        "## Agent Publish\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## 0.1.0\n", encoding="utf-8")

    result = validate_docs_quality(root)

    assert "CHANGELOG.md must contain an Unreleased section." in result.errors
    assert (
        "docs/DEMO_SCRIPT.md missing demo prerequisite or command: docker compose up --build"
        in result.errors
    )


def test_docs_quality_requires_external_proof_transaction_markers(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/readiness/external-proof-matrix.md").write_text(
        "# Outstanding External Proof Matrix\n\n"
        "## How To Use\n\n"
        "## Open External Proof Items\n\n"
        "| Proof area | Workflow / command | Required artifact(s) | "
        "Backfill document | Current state |\n"
        "|---|---|---|---|---|\n"
        "| Hosted browser proof for Phase 0M | ci | artifact | doc | pending |\n\n"
        "## Backfill Rule\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/readiness/external-proof-matrix.md missing required section: "
        "## Completion Transaction" in result.errors
    )
    assert (
        "docs/readiness/external-proof-matrix.md missing required external proof phrase: "
        "Required scorecard row updates" in result.errors
    )


def test_docs_quality_requires_release_proof_report(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/readiness/release-proof-report.md").write_text(
        "# Release Proof Report\n\n"
        "## Workflow Contract\n\n"
        "## Current State\n\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/readiness/release-proof-report.md missing required section: "
        "## Hosted CI Backfill Template" in result.errors
    )


def test_docs_quality_requires_all_phases_ci_proof_report(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/readiness/all-phases-ci-proof.md").write_text(
        "# All-Phases CI Proof\n\n"
        "## Workflow Contract\n\n"
        "## Current State\n\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/readiness/all-phases-ci-proof.md missing required section: "
        "## Hosted CI Backfill Template" in result.errors
    )


def test_docs_quality_requires_hosted_proof_scorecard_row_references(
    tmp_path: Path,
) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/readiness/external-proof-matrix.md").write_text(
        "# Outstanding External Proof Matrix\n\n"
        "## How To Use\n\n"
        "## Open External Proof Items\n\n"
        "| Proof area | Workflow / command | Required artifact(s) | Backfill document | "
        "Required scorecard row updates | Current state |\n"
        "|---|---|---|---|---|---|\n"
        "| Hosted release proof | release | `release-evidence-index`, `release-sbom` | "
        "docs/readiness/release-proof-report.md | rows | pending |\n\n"
        "## Completion Transaction\n\n"
        "Update every scorecard row named in `Required scorecard row updates`.\n\n"
        "## Hosted Evidence Backfill\n\n"
        "## Backfill Rule\n",
        encoding="utf-8",
    )
    (root / "docs/readiness/scorecard.md").write_text(
        "# Production Readiness Scorecard\n\n"
        "## Milestone Status\n\n"
        "Milestone A: Internal Alpha\n"
        "Milestone B: Production Beta\n"
        "Milestone C: External GA\n"
        "Milestone D: Competitive Excellence\n\n"
        "## Early Phase Status\n\n"
        "Phase -3: User Task And Experience Baseline\n"
        "Phase -2: Product Workflow Spec Reconciliation\n"
        "Phase -1A: Frontend Test Harness Baseline\n"
        "Phase -1B: Frontend State Architecture Baseline\n"
        "Phase -1C: Console Aggregate And Permission API Contract\n"
        "Phase 1: Production Truth Baseline\n"
        "Phase 12A: Product Narrative Baseline\n"
        "Phase 12B: Product Trust Assets, Examples, Demo, And Community\n\n"
        "## Milestone A Exit Criteria\n\n"
        "## Milestone B Exit Criteria\n\n"
        "## Milestone C Exit Criteria\n\n"
        "## Milestone D Exit Criteria\n\n"
        "## Definition Of Done Audit\n\n"
        "All phases have passing tests in CI.\n"
        "Every core workflow maps to a named user role, job, decision, risk, success "
        "feedback, and failure recovery path.\n"
        "Generic CRUD coverage is no longer counted as complete unless a workflow has "
        "domain validation, action availability, audit behavior, and browser coverage.\n"
        "Product function coverage review exists and is kept current for all major "
        "product areas, including lifecycle, runtime, governance, exposure, "
        "compatibility, operations, identity, quality, cost, assets, settings, "
        "developer experience, and soft power.\n"
        "Docker Compose smoke passes from a clean checkout.\n"
        "Kubernetes smoke passes in an ephemeral cluster.\n"
        "Release workflow builds, scans, signs or attests, and publishes artifacts.\n\n"
        "## Hosted Evidence Backfill\n\n"
        "Hosted release closeout\n"
        "docs/readiness/release-proof-report.md\n"
        "`release-evidence-index`\n"
        "`release-sbom`\n\n"
        "## Claim Guardrails\n",
        encoding="utf-8",
    )
    (root / "docs/readiness/release-proof-report.md").write_text(
        "# Release Proof Report\n\n"
        "## Workflow Contract\n\n"
        "`release-evidence-index`\n"
        "`release-sbom`\n\n"
        "## Current State\n\n"
        "## Hosted CI Backfill Template\n\n"
        "## Scorecard Rows To Update\n\n"
        "## Closure Verdict\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/readiness/release-proof-report.md missing scorecard row update reference: "
        "`Phase 11: SDK, CLI, And Release Engineering`" in result.errors
    )


def _write_minimal_docs_tree(root: Path) -> Path:
    docs_dir = root / "docs"
    adr_dir = docs_dir / "architecture" / "adrs"
    docs_dir.mkdir()
    adr_dir.mkdir(parents=True)
    (root / "README.md").write_text("# DimooRun\n", encoding="utf-8")

    minimal_docs = {
        "docs/plans/production-grade-gap-closure-2026-06-04.md": "# Plan\n",
        "docs/product/console-user-task-model.md": "# Console User Task Model\n",
        "docs/product/console-experience-acceptance.md": "# Console Experience Acceptance\n",
        "docs/product/workflow-coverage-matrix.md": "# Product Workflow Coverage Matrix\n",
        "docs/product/function-coverage-review.md": "# Product Function Coverage Review\n",
        "docs/product/optimization-backlog.md": "# Product Optimization Backlog\n",
        "docs/readiness/scorecard.md": _minimal_scorecard(),
        "docs/readiness/compose-smoke-report.md": "# Compose Smoke Report\n",
        "docs/readiness/browser-smoke-report.md": "# Browser Smoke Report\n",
        "docs/readiness/placeholders/dashboard-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/agent-detail-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/deployment-workflow-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/run-workbench-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/gateway-route-tester-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/approval-queue-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/settings-danger-zone-desktop.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        "docs/readiness/placeholders/docs-quickstart-mobile.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug report\n",
        ".github/ISSUE_TEMPLATE/feature_request.yml": "name: Feature request\n",
        ".github/pull_request_template.md": "## Summary\n",
    }
    for relative_path, text in {**minimal_docs, **_minimal_phase_12a_docs()}.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _minimal_phase_12a_docs() -> dict[str, str]:
    return {
        path: "\n\n".join(sections) + "\n"
        for path, sections in PHASE_12A_DOCS.items()
    }


def _minimal_scorecard() -> str:
    return "\n".join(
        [
            "# Production Readiness Scorecard",
            "## Milestone Status",
            "| Milestone | Status | Evidence | Remaining gap |",
            "|---|---|---|---|",
            "| Milestone A: Internal Alpha | partial | evidence | gap |",
            "| Milestone B: Production Beta | partial | evidence | gap |",
            "| Milestone C: External GA | missing | evidence | gap |",
            "| Milestone D: Competitive Excellence | missing | evidence | gap |",
            "## Early Phase Status",
            "| Phase | Status | Evidence | Remaining gap |",
            "|---|---|---|---|",
            "| Phase -3: User Task And Experience Baseline | complete | evidence | gap |",
            "| Phase -2: Product Workflow Spec Reconciliation | partial | evidence | gap |",
            "| Phase -1A: Frontend Test Harness Baseline | partial | evidence | gap |",
            "| Phase -1B: Frontend State Architecture Baseline | partial | evidence | gap |",
            "| Phase -1C: Console Aggregate And Permission API Contract | partial | "
            "evidence | gap |",
            "| Phase 1: Production Truth Baseline | partial | evidence | gap |",
            "| Phase 12A: Product Narrative Baseline | partial | evidence | gap |",
            "| Phase 12B: Product Trust Assets, Examples, Demo, And Community | "
            "partial | evidence | gap |",
            "## Milestone A Exit Criteria",
            "## Milestone B Exit Criteria",
            "## Milestone C Exit Criteria",
            "## Milestone D Exit Criteria",
            "## Definition Of Done Audit",
            "| Definition of done item | Status | Evidence | Remaining gap |",
            "|---|---|---|---|",
            "| All phases have passing tests in CI. | partial | evidence | gap |",
            (
                "| Every core workflow maps to a named user role, job, decision, risk, "
                "success feedback, and failure recovery path. | partial | evidence | "
                "gap |"
            ),
            (
                "| Generic CRUD coverage is no longer counted as complete unless a "
                "workflow has domain validation, action availability, audit behavior, "
                "and browser coverage. | partial | evidence | gap |"
            ),
            (
                "| Product function coverage review exists and is kept current for all "
                "major product areas, including lifecycle, runtime, governance, "
                "exposure, compatibility, operations, identity, quality, cost, "
                "assets, settings, developer experience, and soft power. | partial | "
                "evidence | gap |"
            ),
            (
                "| Docker Compose smoke passes from a clean checkout. | partial | "
                "evidence | gap |"
            ),
            (
                "| Kubernetes smoke passes in an ephemeral cluster. | partial | "
                "evidence | gap |"
            ),
            (
                "| Release workflow builds, scans, signs or attests, and publishes "
                "artifacts. | partial | evidence | gap |"
            ),
            "## Claim Guardrails",
        ]
    )
