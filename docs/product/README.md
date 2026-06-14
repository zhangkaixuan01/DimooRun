# Product Documentation

Use this section to understand the product surface without reading internal
design history.

## Start Here

1. [Product Overview](../start/product-overview.md) defines the product boundary
   and non-goals.
2. [Getting Started](../start/getting-started.md) maps the first successful
   evaluator path.
3. [Quickstart](../start/quickstart.md) gives the current local runtime path.

## Current Product Surface

DimooRun currently centers on these workflows:

- package validation, agent versioning, and deployment creation
- deployment activation, task submission, run watching, and run inspection
- worker execution, retries, artifacts, events, replay, and audit evidence
- governance surfaces for policies, approvals, model routing, tool controls,
  secret references, and identity
- Console, CLI, Python SDK, TypeScript SDK, Docker, and Helm entry points

The authoritative maturity status is tracked in
[Current Maturity](../readiness/current-maturity.md) and the
[Production Readiness Scorecard](../readiness/scorecard.md).

## Boundaries

DimooRun is not a prompt IDE, low-code agent builder, drag-and-drop workflow
canvas, or replacement for LangGraph, LangChain Agent, or DeepAgents. It assumes
agent business logic remains in the user's package while runtime behavior is
operated through DimooRun.
