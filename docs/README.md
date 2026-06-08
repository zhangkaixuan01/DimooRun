# DimooRun Documentation

DimooRun is an adapter-first runtime, operations, and governance control plane for AI agents. It is for teams that bring agent code and need safer execution, deployment, observability, policy, replay, and operational evidence.

Current maturity is tracked in [Production Readiness Scorecard](readiness/scorecard.md). The short version is: production-shaped foundation, not an externally production-grade platform yet.

## Start Here

Read these first, in order:

1. [Product Overview](start/product-overview.md) explains what DimooRun is and what it is not.
2. [Getting Started](start/getting-started.md) maps the first successful runtime path.
3. [Quickstart](start/quickstart.md) gives a 15-minute local path with current caveats.
4. [Current Maturity](readiness/current-maturity.md) states what is proven, partial, or missing.
5. [Production Readiness Scorecard](readiness/scorecard.md) is the source of truth for production-grade claims.

## Product

Use these when deciding what workflow to build or evaluate:

- [Console User Task Model](product/console-user-task-model.md)
- [Console Experience Acceptance](product/console-experience-acceptance.md)
- [Product Workflow Coverage Matrix](product/workflow-coverage-matrix.md)
- [Product Function Coverage Review](product/function-coverage-review.md)
- [Product Optimization Backlog](product/optimization-backlog.md)

## Readiness

Use these for maturity, smoke evidence, and release-claim guardrails:

- [Production Readiness Scorecard](readiness/scorecard.md)
- [Current Maturity](readiness/current-maturity.md)
- [Phase 0H Evidence Checklist](readiness/phase-0h-evidence.md)
- [Compose Smoke Report](readiness/compose-smoke-report.md)
- [Browser Smoke Report](readiness/browser-smoke-report.md)
- [Screenshots](readiness/screenshots.md)

## Architecture

Use these for system shape and design decisions:

- [Architecture Overview](architecture/overview.md)
- [Concepts](reference/concepts.md)
- [Design Spec](reference/design-spec.md)
- [ADR 0001: Runtime Control Plane](architecture/adrs/0001-runtime-control-plane.md)

## Plans

Use these for roadmap execution context:

- [Production Grade Gap Closure Plan](plans/production-grade-gap-closure-2026-06-04.md)
- [Pre-Execution Plans](pre_execution_plans/)
- [Superpowers Plans And Specs](superpowers/)

## History

Use these only when you need implementation chronology:

- [Implementation Update 2026-05-30](history/implementation-update-2026-05-30.md)
- [Implementation Update 2026-06-01](history/implementation-update-2026-06-01.md)

## Directory Map

```text
docs/
  start/        first-read product and quickstart guides
  product/      user tasks, workflow coverage, product backlog
  readiness/    maturity scorecards, smoke reports, screenshot evidence
  architecture/ architecture overview and ADRs
  reference/    detailed specs and concepts
  plans/        active production-grade gap closure plans
  history/      dated implementation updates
```
