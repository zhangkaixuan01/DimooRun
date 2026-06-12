# Threat Model

This document captures the main trust boundaries and failure modes for
DimooRun's current product shape. It is not a formal external certification; it
is the repository's truthful working threat model.

## Scope

This threat model covers:

- Console and operator sessions
- native and compatibility APIs
- worker execution and package loading
- secrets, model gateway, and tool gateway paths
- artifact and audit evidence storage

## Assets

The most important assets are:

- tenant/project scoped runtime data
- agent packages and version metadata
- deployment intent and runtime status
- secrets and secret references
- audit records and incident evidence
- artifacts, traces, and request logs

## Trust Boundaries

Main boundaries:

- browser operator session to Console/API
- API layer to persistence and worker systems
- DimooRun runtime to user-supplied agent package code
- worker runtime to external model/tool systems
- object store and audit persistence to operator readers

## Threats By Surface

### Console And Sessions

Risks:

- stolen or replayed operator sessions
- over-broad permissions
- misleading UI state that hides backend denial or stale data

Current mitigations:

- Redis-backed session storage with hashed tokens
- scoped operator permissions
- backend-derived action availability and audit responses on sensitive workflows

### Native And Compatibility APIs

Risks:

- missing scope headers causing cross-scope confusion
- duplicate task submission without idempotency
- compatibility surfaces bypassing governance

Current mitigations:

- tenant/project scope headers on native APIs
- idempotency handling on create paths
- compatibility translation into native runtime/governance paths

### Worker And Package Loading

Risks:

- unsafe local package URIs in non-dev environments
- worker crash leaving leased tasks stuck
- unvalidated agent versions executing in a durable runtime

Current mitigations:

- package URI restrictions outside dev mode
- lease fencing, reaping, and retry/dead-letter handling
- runtime validation for ready versions before execution

### Secrets, Model Gateway, And Tool Gateway

Risks:

- secret exposure in logs or artifacts
- ungoverned external model calls
- high-risk tool calls without approval

Current mitigations:

- secret-reference based package validation
- runtime governance injection for model/tool/secret services
- policy and approval flows with audit evidence

### Artifacts, Audit, And Observability

Risks:

- sensitive payloads captured without redaction
- tampered evidence bundles
- insufficient retention controls

Current mitigations:

- redaction-oriented workflow design
- artifact checksum verification
- separate audit, event, and request-log surfaces

## Mitigations In Repository

Evidence already in the repository includes:

- startup guards for unsafe production settings
- runtime policy and approval integration tests
- worker fencing and recovery tests
- docs guardrails against unsupported maturity claims
- release workflow checks for SBOM, provenance, and changelog presence

## Residual Risks

- hosted infrastructure proof is still incomplete
- screenshot and demo evidence can lag behind implementation
- not every Console workflow is fully hardened against operator confusion
- external package publishing and hosted runtime fetch paths remain incomplete

## Review Boundary

When the runtime model, secrets path, session model, or deployment topology
changes materially, update this document in the same change set.
