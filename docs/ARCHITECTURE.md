# Architecture

## Planes

DimooRun keeps three product planes plus the Console:

```mermaid
flowchart LR
    Console[Vue Console] --> Control[Control Plane API]
    Control --> Runtime[Runtime Plane]
    Runtime --> Agent[Agent Plane]
    Control --> Governance[Governance and Audit]
    Runtime --> Observability[Events, Artifacts, Traces, Metrics]
```

- Control Plane: APIs, package/version/deployment metadata, governance, identity, admin resources, and Console aggregates.
- Runtime Plane: task submission, leases, attempts, runs, events, replay, cancellation, retries, and worker coordination.
- Agent Plane: adapter-loaded user agent code and framework compatibility boundaries.
- Console: operator workflows backed by typed APIs and aggregate read models.

## Runtime Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Queue
    participant Worker
    participant Adapter
    participant Store
    User->>API: submit task
    API->>Store: create task and run
    API->>Queue: enqueue task
    Worker->>Queue: lease task
    Worker->>Adapter: invoke agent code
    Adapter-->>Worker: events/output/error
    Worker->>Store: persist attempts, events, artifacts
    User->>API: inspect run
```

## Governance Decision Path

```mermaid
flowchart TD
    Request[State-changing request] --> Auth[Authenticate actor]
    Auth --> Permission[Check permission]
    Permission --> Policy[Evaluate policy]
    Policy --> Approval{Human approval required?}
    Approval -->|yes| HumanTask[Persist human task]
    Approval -->|no| Action[Execute action]
    HumanTask --> Resume[Resume after decision]
    Action --> Audit[Write audit evidence]
    Resume --> Audit
```

High-risk actions should show disabled reasons, required permissions, policy warnings, audit requirements, impact preview, and rollback guidance before submit.

## Compatibility Path

Compatibility APIs and adapters let users bring LangGraph, LangChain Agent, and DeepAgents code without bypassing native governance. Unsupported capabilities must be reported as gaps, not hidden behind optimistic claims.

## Observability Path

Runtime observability separates events, traces, artifacts, metrics, and audit records. The target is queryable, redacted evidence that helps operators classify failures, replay safely, and explain decisions.

