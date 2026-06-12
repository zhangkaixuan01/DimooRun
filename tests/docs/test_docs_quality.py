import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.docs_quality import validate_docs_quality  # noqa: E402

PHASE_12A_DOCS = {
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
    ],
    "docs/readiness/browser-smoke-report.md": [
        "# Browser Smoke Report",
        "## Command",
        "## Result",
        "## Evidence",
        "## Next Action",
    ],
    "docs/architecture/adrs/0001-runtime-control-plane.md": [
        "# ADR 0001: Runtime Control Plane",
        "## Decision",
        "## Consequences",
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
            "| Milestone | Status | Evidence | Remaining gap |",
            "|---|---|---|---|",
            "| Milestone A: Internal Alpha | partial | evidence | gap |",
            "| Milestone B: Production Beta | partial | evidence | gap |",
            "| Milestone C: External GA | missing | evidence | gap |",
            "| Milestone D: Competitive Excellence | missing | evidence | gap |",
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
        ]
    )
