# Product Overview

## What DimooRun Is

DimooRun is a runtime control plane for production-shaped agent systems. It wraps agent code with runtime APIs, durable task execution, deployment controls, governance, audit evidence, observability, replay, quality loops, and operator workflows.

The core boundary is:

```text
Business logic is a black box.
Runtime behavior is a white box.
```

Users bring LangGraph, LangChain Agent, DeepAgents, or compatible adapter code. DimooRun focuses on registering, validating, deploying, invoking, inspecting, replaying, governing, and operating that code.

## Why It Exists

Generic agent frameworks help build agents. Production teams still need answers to operational questions:

- Which version handled this run?
- Why did a task fail or retry?
- Was a tool/model/secret action allowed by policy?
- Can this deployment be promoted or rolled back safely?
- What evidence proves a replay, approval, incident, or restore decision?

DimooRun exists to make those runtime and governance answers explicit.

## Core Workflows

- Agent package registration and version readiness.
- Deployment promotion, pause, resume, drain, restart, and rollback.
- Task submission, run inspection, failure triage, retry, and replay.
- Policy, human approval, model/tool/secret governance.
- Dataset, experiment, evaluation, and quality gate evidence.
- Published surface, ingress, compatibility, identity, settings, operations, cost, scheduled/batch, and catalog workflows as later production-grade phases.

## Non-Goals

DimooRun is not:

- a low-code agent builder;
- a drag-and-drop workflow canvas;
- a prompt design platform;
- a business application builder;
- a full billing or wallet product;
- a generic ITSM or ticketing system;
- a replacement for professional model gateways where integration is the right boundary.

## Current Maturity

The project has broad architecture and implementation foundations, but many product workflows remain partial. Use [Current Maturity](../readiness/current-maturity.md) and [Production Readiness Scorecard](../readiness/scorecard.md) before making deployment claims.

