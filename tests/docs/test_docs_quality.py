import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.docs_quality import REQUIRED_SECTIONS, validate_docs_quality  # noqa: E402


def test_docs_quality_passes_for_current_repo() -> None:
    result = validate_docs_quality(ROOT)

    assert result.errors == []


def test_public_docs_exist_with_required_sections() -> None:
    for relative_path, required_sections in REQUIRED_SECTIONS.items():
        path = ROOT / relative_path
        assert path.exists(), f"Missing required doc: {relative_path}"
        text = path.read_text(encoding="utf-8")
        for section in required_sections:
            assert section in text, f"{relative_path} missing section: {section}"


def test_scorecard_records_public_milestone_statuses() -> None:
    scorecard = (ROOT / "docs/readiness/scorecard.md").read_text(encoding="utf-8")

    for milestone in [
        "Milestone A: Internal Alpha",
        "Milestone B: Production Beta",
        "Milestone C: External GA",
        "Milestone D: Competitive Excellence",
    ]:
        assert milestone in scorecard

    assert "Production-shaped foundation: yes." in scorecard
    assert "External production-grade platform: not yet." in scorecard


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
        "## Screenshot Evidence\n\n"
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


def test_docs_quality_flags_broken_internal_links(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/README.md").write_text(
        "# DimooRun Documentation\n\n"
        "## Start Here\n\n"
        "[Missing](MISSING.md)\n\n",
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
        "## Screenshot Evidence\n\n"
        "![Missing](docs/readiness/missing.svg)\n\n"
        "## Supported Modes\n\n"
        "## Current Maturity\n\n"
        "## What DimooRun Is Not\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert "Broken image reference in README.md: docs/readiness/missing.svg" in result.errors


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
        "## Screenshot Evidence\n\n"
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


def test_docs_quality_requires_demo_prerequisites_and_unreleased_changelog(
    tmp_path: Path,
) -> None:
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


def test_docs_quality_rejects_stale_deleted_doc_references(tmp_path: Path) -> None:
    root = _write_minimal_docs_tree(tmp_path)
    (root / "docs/README.md").write_text(
        "# DimooRun Documentation\n\n"
        "## Start Here\n\n"
        "[Old](product/workflow-coverage-matrix.md)\n",
        encoding="utf-8",
    )

    result = validate_docs_quality(root)

    assert (
        "docs/README.md contains stale docs reference: workflow-coverage-matrix.md"
        in result.errors
    )


def test_compatibility_examples_are_runnable_and_documented() -> None:
    root = ROOT / "examples/compatibility/langgraph-basic"
    assert (root / "README.md").exists()
    assert (root / "compat_flow.py").exists()
    assert (root / "source" / "langgraph.json").exists()
    readme = (root / "README.md").read_text(encoding="utf-8")
    required = [
        "Create assistant",
        "Create thread",
        "Create run",
        "Stream events",
        "Replay events",
        "Cancel run",
        "Migration report",
        "Native Run and Task evidence",
    ]
    for phrase in required:
        assert phrase in readme


def test_evidence_gallery_lists_required_product_screens() -> None:
    gallery = (ROOT / "docs/readiness/evidence-gallery.md").read_text(encoding="utf-8")
    required = [
        "Dashboard",
        "Agent detail",
        "Deployment workflow",
        "Run workbench",
        "Published surface route tester",
        "Approval queue",
        "Settings danger zone",
        "Quickstart activation path",
    ]
    for item in required:
        assert item in gallery


def _write_minimal_docs_tree(root: Path) -> Path:
    minimal_docs = {
        relative_path: "\n\n".join(sections) + "\n"
        for relative_path, sections in REQUIRED_SECTIONS.items()
    }
    minimal_docs.update(
        {
            "docs/readiness/scorecard.md": _minimal_scorecard(),
            "README.md": _minimal_readme(),
            "docs/README.md": _minimal_docs_home(),
            "docs/start/quickstart.md": _minimal_quickstart(),
            "docs/DEMO_SCRIPT.md": _minimal_demo_script(),
            "docs/TRUST_AND_SECURITY.md": _minimal_trust_doc(),
            "docs/COMPARISONS.md": _minimal_comparisons(),
            "CHANGELOG.md": (
                "# Changelog\n\n## Unreleased\n\n- Phase 12B trust and security docs."
                "\n\n## 0.1.0\n"
            ),
            ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug report\n",
            ".github/ISSUE_TEMPLATE/feature_request.yml": "name: Feature request\n",
            ".github/pull_request_template.md": "## Summary\n",
        }
    )
    for relative_path, text in minimal_docs.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _minimal_readme() -> str:
    return (
        "# DimooRun\n\n"
        "## Why Teams Use DimooRun\n\n"
        "examples/langgraph/support-agent\n\n"
        "## First 15 Minutes\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "docker compose up --build\n"
        "```\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "uv run dimoorun run watch\n"
        "```\n\n"
        "## Architecture Signal\n\n"
        "## Screenshot Evidence\n\n"
        "## Supported Modes\n\n"
        "## Current Maturity\n\n"
        "Production-shaped foundation: yes.\n"
        "External production-grade platform: not yet.\n\n"
        "## What DimooRun Is Not\n"
    )


def _minimal_docs_home() -> str:
    return (
        "# DimooRun Documentation\n\n"
        "Production-shaped foundation: yes.\n"
        "External production-grade platform: not yet.\n\n"
        "## Start Here\n\n"
        "## Evaluation Path\n\n"
        "## Product\n\n"
        "## API And SDK\n\n"
        "## Readiness\n\n"
        "## Trust And Operations\n\n"
        "## Examples\n\n"
        "## Community\n\n"
        "## Known Gaps\n\n"
        "## Directory Map\n"
    )


def _minimal_quickstart() -> str:
    return (
        "# Quickstart\n\n"
        "Production-shaped foundation: yes.\n"
        "External production-grade platform: not yet.\n\n"
        "## Working Directory\n\n"
        "examples/langgraph/support-agent\n"
        "http://127.0.0.1:8080\n"
        "dev-local-key\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "docker compose up --build\n"
        "```\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "uv run dimoorun run watch\n"
        "```\n\n"
        "## Verify The Run\n"
    )


def _minimal_demo_script() -> str:
    return (
        "# Demo Script\n\n"
        "Production-shaped foundation: yes.\n"
        "External production-grade platform: not yet.\n\n"
        "examples/langgraph/support-agent\n"
        "http://127.0.0.1:8080\n"
        "dev-local-key\n\n"
        "## Prerequisites\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "docker compose up --build\n"
        "```\n\n"
        "Working directory: repository root.\n\n"
        "```bash\n"
        "uv run dimoorun run watch\n"
        "```\n\n"
        "## Agent Publish\n\n"
        "## Deployment Promote\n\n"
        "## Run Inspect\n\n"
        "## Replay\n\n"
        "## Policy Approval\n\n"
        "## Gateway Route Test\n\n"
        "## Incident Triage\n\n"
        "## Cost Drilldown\n"
    )


def _minimal_trust_doc() -> str:
    return (
        "# Trust And Security\n\n"
        "[Security Policy](../SECURITY.md)\n"
        "[Threat Model](THREAT_MODEL.md)\n"
        "[Operations Runbook](OPERATIONS_RUNBOOK.md)\n\n"
        "## Security Posture\n\n"
        "## Security Reporting\n\n"
        "## Dependency And Supply Chain Checks\n\n"
        "## Secret Handling Model\n\n"
        "## Production Safety Defaults\n"
    )


def _minimal_comparisons() -> str:
    return (
        "# Comparisons\n\n"
        "## Versus A Plain LangGraph App\n\n"
        "### Evidence In Repository\n\n"
        "## Versus LangGraph Platform-Style Compatibility\n\n"
        "### Evidence In Repository\n\n"
        "## Versus Generic Workflow Engines\n\n"
        "### Evidence In Repository\n\n"
        "## Versus Model Gateways\n\n"
        "### Evidence In Repository\n"
    )


def _minimal_scorecard() -> str:
    return (
        "# Production Readiness Scorecard\n\n"
        "Production-shaped foundation: yes.\n"
        "External production-grade platform: not yet.\n\n"
        "## Milestone Status\n\n"
        "| Milestone | Status | Evidence | Remaining gap |\n"
        "|---|---|---|---|\n"
        "| Milestone A: Internal Alpha | partial | evidence | gap |\n"
        "| Milestone B: Production Beta | partial | evidence | gap |\n"
        "| Milestone C: External GA | missing | evidence | gap |\n"
        "| Milestone D: Competitive Excellence | missing | evidence | gap |\n\n"
        "## Current Strengths\n\n"
        "## Remaining Gaps\n\n"
        "## Claim Guardrails\n"
    )
