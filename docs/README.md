# DimooRun Documentation

DimooRun is an adapter-first runtime, operations, and governance control plane
for AI agents. These docs are organized for a serious evaluator who wants to
understand the product, run the first happy path, and see what is still missing
without reverse-engineering the repository.

Current maturity is tracked in [Production Readiness Scorecard](readiness/scorecard.md).
The short version is: production-shaped foundation, not an externally
production-grade platform yet.

## Start Here

Read these first, in order:

1. [Product Overview](start/product-overview.md) explains what DimooRun is and what it is not.
2. [Getting Started](start/getting-started.md) maps the first successful runtime path.
3. [Quickstart](start/quickstart.md) gives a 15-minute local path with current caveats.
4. [Current Maturity](readiness/current-maturity.md) states what is proven, partial, or missing.
5. [Production Readiness Scorecard](readiness/scorecard.md) is the source of truth for production-grade claims.

## Evaluation Path

Use this order when you are evaluating whether the product is coherent:

1. Read [Product Overview](start/product-overview.md) for scope and boundaries.
2. Run [Quickstart](start/quickstart.md) to publish, deploy, submit, and inspect a real example.
3. Open [Architecture Overview](architecture/overview.md) to see the control/runtime/worker split.
4. Read [Current Maturity](readiness/current-maturity.md) before treating any workflow as production proof.

## Product

Use these when deciding what workflow to build or evaluate:

- [Product Overview](start/product-overview.md)
- [Getting Started](start/getting-started.md)
- [Quickstart](start/quickstart.md)
- [Console User Task Model](product/console-user-task-model.md)
- [Console Experience Acceptance](product/console-experience-acceptance.md)
- [Product Workflow Coverage Matrix](product/workflow-coverage-matrix.md)
- [Product Function Coverage Review](product/function-coverage-review.md)
- [Product Optimization Backlog](product/optimization-backlog.md)

## API And SDK

Use these when you want to automate the product instead of clicking through the
Console:

- [Architecture Overview](architecture/overview.md)
- [Concepts](reference/concepts.md)
- [Design Spec](reference/design-spec.md)
- [Repository README](../README.md)

## Readiness

Use these for maturity, smoke evidence, and release-claim guardrails:

- [Production Readiness Scorecard](readiness/scorecard.md)
- [Current Maturity](readiness/current-maturity.md)
- [Phase 0H Evidence Checklist](readiness/phase-0h-evidence.md)
- [Compose Smoke Report](readiness/compose-smoke-report.md)
- [Browser Smoke Report](readiness/browser-smoke-report.md)
- [Screenshots](readiness/screenshots.md)

## Trust And Operations

Use these when you want to evaluate security posture, operational expectations,
and failure handling:

- [Trust And Security](TRUST_AND_SECURITY.md)
- [Threat Model](THREAT_MODEL.md)
- [Operations Runbook](OPERATIONS_RUNBOOK.md)
- [Security Policy](../SECURITY.md)

## Architecture

Use these for system shape and design decisions:

- [Architecture Overview](architecture/overview.md)
- [Concepts](reference/concepts.md)
- [Design Spec](reference/design-spec.md)
- [ADR 0001: Runtime Control Plane](architecture/adrs/0001-runtime-control-plane.md)

## Examples

Use these for realistic framework-specific packages and evaluator workflows:

- [LangGraph support-agent](../examples/langgraph/support-agent/README.md)
- [LangChain Agent support-agent](../examples/langchain-agent/support-agent/README.md)
- [DeepAgents support-agent](../examples/deepagents/support-agent/README.md)
- [Demo Script](DEMO_SCRIPT.md)

## Community

Use these when contributing, reporting issues, or tracking product direction:

- [Contributing Guide](../CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [FAQ](FAQ.md)
- [Changelog](../CHANGELOG.md)

## Known Gaps

- Clean-machine Compose and ephemeral Kubernetes smoke evidence is still incomplete.
- Screenshot placeholders exist, but generated product screenshots are not yet complete.
- Hosted deployment proof, generated screenshots, and broader trust verification
  evidence are still incomplete.

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
