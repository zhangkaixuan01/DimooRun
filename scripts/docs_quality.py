from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_DOCS = [
    "docs/plans/production-grade-gap-closure-2026-06-04.md",
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
    "docs/readiness/browser-smoke-report.md",
    "docs/architecture/adrs/0001-runtime-control-plane.md",
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

REQUIRED_MILESTONES = [
    "Milestone A: Internal Alpha",
    "Milestone B: Production Beta",
    "Milestone C: External GA",
    "Milestone D: Competitive Excellence",
]

REQUIRED_PHASES = [
    "Phase -3: User Task And Experience Baseline",
    "Phase -2: Product Workflow Spec Reconciliation",
    "Phase -1A: Frontend Test Harness Baseline",
    "Phase -1B: Frontend State Architecture Baseline",
    "Phase -1C: Console Aggregate And Permission API Contract",
    "Phase 1: Production Truth Baseline",
    "Phase 12A: Product Narrative Baseline",
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


@dataclass(frozen=True)
class DocsQualityResult:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


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

    return DocsQualityResult(errors=errors)


def _validate_scorecard(scorecard: str) -> list[str]:
    errors: list[str] = []

    if "# Production Readiness Scorecard" not in scorecard:
        errors.append("Readiness scorecard must start with '# Production Readiness Scorecard'.")

    for milestone in REQUIRED_MILESTONES:
        if milestone not in scorecard:
            errors.append(f"Readiness scorecard missing {milestone}.")

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
    return sorted((root / "docs").rglob("*.md")) + [root / "README.md"]


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
