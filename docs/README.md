# DimooRun Documentation

DimooRun is an adapter-first runtime, operations, and governance control plane
for AI agents. These docs are organized for readers who want to understand the
product, run the first path, and check the current readiness boundary without
digging through internal planning records.

Current maturity:

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

## Start Here

Read these first, in order:

1. [Product Overview](start/product-overview.md) explains what DimooRun is and
   what it is not.
2. [Getting Started](start/getting-started.md) maps the first successful runtime
   path.
3. [Quickstart](start/quickstart.md) gives a 15-minute local path with current
   caveats.
4. [Current Maturity](readiness/current-maturity.md) states what is proven,
   partial, or missing.

## Evaluation Path

Use this order when evaluating the project:

1. Read [Product Overview](start/product-overview.md) for scope and boundaries.
2. Run [Quickstart](start/quickstart.md) to publish, deploy, submit, and inspect
   a real example.
3. Open [Architecture Overview](architecture/overview.md) to see the
   control/runtime/worker split.
4. Read [Readiness](readiness/README.md) before treating any workflow as
   production proof.

## Product

- [Product Documentation](product/README.md)
- [Product Overview](start/product-overview.md)
- [Getting Started](start/getting-started.md)
- [Quickstart](start/quickstart.md)

## API And SDK

Use these when automating the product instead of clicking through the Console:

- [Architecture Overview](architecture/overview.md)
- [Concepts](reference/concepts.md)
- [Repository README](../README.md)

## Readiness

- [Readiness](readiness/README.md)
- [Current Maturity](readiness/current-maturity.md)
- [Production Readiness Scorecard](readiness/scorecard.md)

## Trust And Operations

- [Trust And Security](TRUST_AND_SECURITY.md)
- [Threat Model](THREAT_MODEL.md)
- [Operations Runbook](OPERATIONS_RUNBOOK.md)
- [Security Policy](../SECURITY.md)

## Examples

- [LangGraph support-agent](../examples/langgraph/support-agent/README.md)
- [LangChain Agent support-agent](../examples/langchain-agent/support-agent/README.md)
- [DeepAgents support-agent](../examples/deepagents/support-agent/README.md)
- [Demo Script](DEMO_SCRIPT.md)

## Community

- [Contributing Guide](../CONTRIBUTING.md)
- [Roadmap](ROADMAP.md)
- [FAQ](FAQ.md)
- [Changelog](../CHANGELOG.md)

## Known Gaps

- Clean-machine Compose and ephemeral Kubernetes smoke evidence is still
  incomplete.
- Generated product screenshots are not tracked as committed docs right now.
- Hosted deployment proof, release proof, and broader external trust
  verification are still incomplete.

## Directory Map

```text
docs/
  start/        first-read product and quickstart guides
  product/      concise product documentation index
  readiness/    maturity and readiness scorecard
  architecture/ architecture overview and ADRs
  reference/    concepts reference
```
