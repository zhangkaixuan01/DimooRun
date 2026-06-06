# Concepts

## Resource Model

DimooRun uses scoped resources. Tenant, project, and environment define where runtime and governance actions apply. Core runtime resources include agents, versions, deployments, tasks, runs, attempts, events, artifacts, replay jobs, policies, approvals, service accounts, and audit logs.

Numeric IDs are used for internal managed resources. String identifiers are reserved for protocol and external boundaries such as request IDs, trace IDs, worker IDs, idempotency keys, and object storage URIs.

## Runtime Evidence

Runtime evidence is the material an operator or auditor uses to explain what happened:

- task and run status;
- attempt lifecycle;
- ordered events;
- artifacts and checksums;
- trace IDs;
- policy decisions;
- human approvals;
- audit records;
- deployment/version context;
- replay or quality evidence.

Evidence must preserve runtime facts without exposing secret values or hidden payloads.

## Workflow Completeness

A route, table, and edit form do not make a workflow complete. A production-grade workflow needs:

- named user role and job;
- pre-action context;
- domain validation;
- permission and policy summary;
- audit behavior;
- success feedback;
- failure recovery;
- browser evidence.

The current workflow status is tracked in [Product Workflow Coverage Matrix](PRODUCT_WORKFLOW_COVERAGE_MATRIX.md).

## Idempotency And Request Identity

Write APIs should have stable request identity and idempotency where duplicate submission could cause unsafe behavior. The target production contract is documented in the gap closure plan; not every write path is complete yet.

