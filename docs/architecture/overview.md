# Architecture

## Control Plane

```mermaid
flowchart LR
    Console[Console UI] --> NativeAPI[Native and Admin APIs]
    NativeAPI --> Metadata[(Agents Versions Deployments Identity Policy)]
    NativeAPI --> Aggregates[Console aggregate read models]
    NativeAPI --> Audit[Audit log sink]
```

The control plane owns metadata, identity, policy, admin routes, and Console
aggregates.

## Runtime Plane

```mermaid
flowchart LR
    Submit[Task submission] --> RunStore[(Runs Tasks Attempts Events)]
    RunStore --> Queue[Queue and leasing backend]
    Queue --> Replay[Replay and retry services]
    Replay --> RunStore
```

The runtime plane owns task lifecycle, retries, replay, cancellation, and the
durable evidence model around execution.

## Agent Plane

```mermaid
flowchart LR
    Package[Agent package] --> Adapter[Adapter loader]
    Adapter --> Entrypoint[Framework entrypoint]
    Entrypoint --> Logic[User agent logic]
    Logic --> Output[Invoke stream interrupt output]
```

The agent plane is where user code runs. DimooRun should wrap it, not replace
it.

## Planes

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

## Worker Loop

```mermaid
sequenceDiagram
    participant Worker
    participant Backend as Task Backend
    participant Store as Run Store
    participant Adapter
    Worker->>Backend: lease task
    Backend-->>Worker: task payload + fencing token
    Worker->>Store: create or resume attempt
    Worker->>Adapter: invoke or stream agent
    Adapter-->>Worker: events, output, interrupt, error
    Worker->>Store: persist attempt, events, artifacts
    Worker->>Backend: complete, retry, or requeue
```

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

High-risk actions should show disabled reasons, required permissions, policy
warnings, audit requirements, impact preview, and rollback guidance before
submit.

## Compatibility Path

```mermaid
flowchart LR
    ExternalClient[Compatibility client] --> CompatAPI[Compatibility API]
    CompatAPI --> Translator[Request translation]
    Translator --> NativeRuntime[Native runtime model]
    NativeRuntime --> Governance[Policy and audit]
    NativeRuntime --> Adapter[Adapter execution]
```

Compatibility APIs and adapters let users bring LangGraph, LangChain Agent, and
DeepAgents code without bypassing native governance. Unsupported capabilities
must be reported as gaps, not hidden behind optimistic claims.

## Observability Path

```mermaid
flowchart LR
    Worker[Worker execution] --> Events[Run events]
    Worker --> Traces[Trace and request ids]
    Worker --> Artifacts[Artifacts and checksums]
    Control[Control plane actions] --> Audit[Audit records]
    Events --> Console[Console and API readers]
    Traces --> Console
    Artifacts --> Console
    Audit --> Console
```

Runtime observability separates events, traces, artifacts, metrics, and audit
records. The target is queryable, redacted evidence that helps operators
classify failures, replay safely, and explain decisions.

