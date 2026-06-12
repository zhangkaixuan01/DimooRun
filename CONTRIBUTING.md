# Contributing

DimooRun accepts contributions that improve product truth, runtime safety,
workflow completeness, docs quality, and verification evidence.

## Before You Start

- read [docs/README.md](docs/README.md)
- read [docs/ROADMAP.md](docs/ROADMAP.md)
- read [docs/readiness/scorecard.md](docs/readiness/scorecard.md)
- prefer issues or change descriptions that explain user workflow impact

## Development Setup

Working directory: repository root.

```bash
uv sync
```

Working directory: `apps/console`.

```bash
npm install
```

## Coding Standards

- keep claims conservative and backed by evidence
- prefer adapter/runtime boundaries over framework-specific shortcuts
- preserve tenant/project/environment scope semantics
- use `apply_patch` for manual file edits when working through Codex workflows
- do not merge unrelated cleanup into a workflow-focused change without reason

## Test Expectations

Before proposing a non-trivial change, run the relevant checks. The broad local
baseline is:

Working directory: repository root.

```bash
uv run ruff check apps tests packages/sdk-python scripts migrations
uv run mypy apps/server tests packages/sdk-python scripts
uv run pytest -q
```

For Console changes, also run:

Working directory: `apps/console`.

```bash
npm run test
npm run test:unit
npm run build
```

## Documentation Expectations

- update docs when workflow behavior or maturity claims change
- keep README, scorecard, and quickstart aligned
- do not add unsupported production claims
- if you add a new product asset, extend `scripts/docs_quality.py` and its tests when appropriate

## Pull Requests

- explain the user or operator workflow affected
- include verification commands actually run
- call out known risks or incomplete evidence
- keep PRs atomic when possible

## Release Expectations

Release-facing changes should keep these artifacts aligned:

- `CHANGELOG.md`
- `scripts/release_check.py`
- release workflow expectations in `.github/workflows/release.yml`

## Community Boundary

This repository values high-signal issues and PRs more than volume. Prefer
concrete evidence, reproduction steps, and scope-aware proposals over general
feature dumping.
