# ADR 0001: Runtime Control Plane

## Status

Accepted as the product architecture direction.

## Context

Agent frameworks help teams build agents, but production operation requires runtime control, governance, evidence, deployment safety, failure recovery, and compatibility boundaries. DimooRun should not become a low-code builder, prompt design platform, workflow canvas, model gateway clone, or generic ticketing system.

## Decision

DimooRun will be an adapter-first runtime control plane. Users bring agent
code. DimooRun provides the APIs, worker runtime, deployment controls,
policy/audit path, observability evidence, replay, quality loop, Console
workflows, and compatibility surface needed to operate that code safely.

The architecture keeps four surfaces:

- Control Plane for APIs, metadata, identity, policy, and admin workflows.
- Runtime Plane for tasks, runs, attempts, events, leases, workers, replay, and cancellation.
- Agent Plane for adapter-loaded user code.
- Console for operator workflows backed by typed APIs and aggregate read models.

## Why This Decision

- It preserves framework choice.
- It makes runtime evidence a first-class product concern.
- It lets governance and deployment controls evolve without forcing agent code rewrites.

## Consequences

- Generic CRUD cannot be counted as a complete product workflow.
- High-risk actions need backend-derived action availability, policy decisions, audit records, and recovery guidance.
- Business logic remains a black box; runtime behavior becomes inspectable evidence.
- Compatibility layers must preserve governance instead of bypassing native controls.
- Product documentation must state current maturity conservatively until executable proof catches up.

