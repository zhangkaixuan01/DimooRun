# Production Readiness Scorecard

This scorecard is the public source of truth for production-grade claims.
It intentionally avoids internal phase history and records only the current
reader-facing maturity boundary.

```text
Production-shaped foundation: yes.
External production-grade platform: not yet.
```

## Milestone Status

| Milestone | Status | Evidence | Remaining gap |
|---|---|---|---|
| Milestone A: Internal Alpha | partial | Core runtime, Console, CLI, SDK, examples, docs, and local verification paths exist. | Current hosted proof and generated screenshot evidence are still incomplete. |
| Milestone B: Production Beta | partial | Worker hardening, governance, observability, Docker, Helm, operations, and trust docs exist. | Clean-machine Compose, ephemeral Kubernetes, release, and broader external evidence are not complete. |
| Milestone C: External GA | missing | Some GA-shaped surfaces exist, including SDKs, CLI, compatibility, identity, admin, and deployment assets. | External hosted proof, release proof, trust verification, and full workflow evidence are missing. |
| Milestone D: Competitive Excellence | missing | Product direction is clear around adapter-first runtime control. | Guided activation, polished operator workflows, exhaustive examples, and differentiated product proof remain incomplete. |

## Current Strengths

- Adapter-first architecture for LangGraph, LangChain Agent, and DeepAgents.
- Native runtime model for agents, versions, deployments, tasks, runs, events,
  attempts, artifacts, replay, policy, approvals, and audit evidence.
- Console, CLI, Python SDK, TypeScript SDK, Docker Compose, Helm, and example
  agent paths are present.
- Trust, security, operations, comparison, roadmap, FAQ, demo, contribution, and
  security policy docs are present.

## Remaining Gaps

- Hosted CI proof is not yet enough to support external production-grade claims.
- Clean-machine Compose and ephemeral Kubernetes smoke results are not complete.
- Generated screenshot evidence is not maintained as a public docs gallery.
- Release attestation, externally hosted trust verification, and full operator
  workflow proof still need closure.

## Claim Guardrails

- It is accurate to say DimooRun has a production-shaped foundation.
- It is not accurate to say DimooRun is externally production-ready.
- Treat unverified workflows as partial even when routes, tests, or docs exist.
- Keep README, quickstart, maturity docs, and examples aligned on the same
  supported commands and caveats.
