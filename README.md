# DimooRun

DimooRun is an adapter-first enterprise runtime platform for AI agents.

The project starts with LangGraph compatibility and keeps the early adapter
roadmap focused on the LangChain ecosystem: LangGraph, LangChain Agents, and
DeepAgents.

## Positioning

DimooRun is not a new agent framework, a low-code agent builder, or a workflow
canvas. It provides the production runtime layer around agents:

- Runtime APIs for invoke, stream, task, resume, cancel, and retry.
- Worker execution, task leasing, retries, idempotency, and event recording.
- Agent package registration, versioning, deployment, and compatibility checks.
- Policy, permissions, secrets, model gateway integration, audit, and observability.
- LangGraph compatibility mode for lower-friction migration.

Core boundary:

```text
Business logic is a black box.
Runtime behavior is a white box.
```

## Current Status

This repository is in the early implementation stage. Phases `01` through `09`
are MVP-complete and test-green, but they should not be read as production
complete. Several runtime services deliberately remain in-process or in-memory
until the production foundation phases wire durable storage, queues, generated
SDKs, and process orchestration.

The primary artifact is [DESIGN_SPEC.md](DESIGN_SPEC.md), which describes the
target architecture, runtime model, compatibility strategy, MVP scope, and
roadmap.

Implemented MVP phase slices:

- `01-project-foundation`: FastAPI server scaffold, configuration models,
  Worker entrypoint, Vue Console scaffold, examples, OpenAPI output directory,
  and baseline tests.
- `02-domain-persistence-and-api`: SQLAlchemy domain models, Alembic migrations,
  repository boundaries, Native/Admin API contract skeletons, audit and soft
  delete semantics, idempotency records, placeholder metadata tables, and
  generated OpenAPI.
- `03-agent-package-and-adapters`: Agent Package manifest validation, package
  entrypoint loading, RuntimeContext, AgentAdapter contract, capability model,
  adapter version metadata, conformance report scaffold, event identity fields,
  LangGraphAdapter, LangChainAgentAdapter, and DeepAgentsAdapter. Package
  loading uses temporary module-path isolation for local package helpers.
  Checkpoint, resume, and cancel are intentionally not certified until the
  Worker and persistence runtime are connected.
- `04-runtime-task-worker-streaming`: Runtime state machines, idempotency
  store, InMemory task backend, lease reaper, fencing token checks, replay
  buffer, SSE encoding, checkpoint index scaffold, replay scheduler scaffold,
  and Worker executor fake-adapter invoke / stream execution paths. Stream
  events are appended incrementally, retryable failures emit `task.retrying`
  without marking the Run terminal, and terminal failures emit `run.failed` /
  `stream.failed`. Event `sequence` and `event_id` are required fields with a
  per-run sequence uniqueness constraint. The in-memory lease reaper requeues
  expired leased and running tasks so worker loss does not leave tasks stuck.
  Worker success first validates task ownership/fencing, then persists Run /
  Attempt success and terminal events, and only then completes the Task.
- `05-deployment-runtime-control`: Deployment desired-status control,
  AgentInstance cache semantics, runtime-status aggregation, Deployment API
  control routes, RunManager deployment gating, and governed PublishedSurface /
  IngressRoute boundaries.
- `06-governance-security-and-model-gateway`: RBAC resource/action permissions,
  ServiceAccounts, API Key authentication, Policy Engine decisions and audit
  records, Deployment API Bearer API Key scope checks, Tool Gateway approval
  boundaries, SecretProvider policy checks, Model Gateway / New API
  configuration and runtime-use boundaries with tenant/project scope validation,
  HITL tasks, Catalog, Prompt/Config/Template assets, Sandbox Policy, and
  hardened governance tables.
- `07-observability-replay-and-quality`: Event / Trace / Audit separation,
  redaction and sampling policies, in-memory Artifact Store with checksum,
  read-time checksum verification, permission and tenant/project checks,
  Run Graph projection with persistable node edges, ReplayJob service with
  runtime override propagation, Dataset scope checks, Experiment / Evaluation /
  Quality Gate contracts, Semantic Store provider metadata, Notification /
  Alert incident flow, and hardened observability / quality tables.
- `08-console-product-plan`: product-grade Vue Runtime Control Plane Console
  with Dashboard, Agents, Deployments, Compatibility, Published Surfaces, Runs,
  Run Detail, Tasks, Events, Debug / Replay, Human Tasks, Policies, API Keys,
  Settings, Chinese / English switching, light / dark theme switching, high-risk
  operation confirmation, ECharts runtime trends, GSAP-scoped page motion, and
  frontend contract tests. The default UI data path still uses mock data for
  product validation; a `nativeConsoleClient` and `VITE_DIMOORUN_*` environment
  boundary now exist for wiring real backend calls.
- `09-sdk-cli-compatibility-and-migration`: `dimoorun` CLI entrypoint, project
  configuration model, `init` / `validate` / `doctor` / `migrate langgraph` /
  `migrate aegra` / `migrate langgraph-platform`, LangGraph Compatibility API
  routes for assistants / threads / runs / SSE stream backed by RunManager,
  TaskBackend, deployment gate checks when a referenced Deployment exists,
  tenant / project scoped API keys, and AuditLog, Agent Protocol
  capability skeleton, best-effort migration reports with source-specific
  warnings, a minimal Native Agents / AgentVersions / Runs / Tasks API backed by
  an in-process runtime store, Python SDK error-code and idempotency-key
  handling with a real Native API integration test, and TypeScript SDK
  placeholder boundary.

Current verification baseline:

```text
uv run pytest -q
uv run ruff check apps tests packages\sdk-python
cd apps/console && npm run test
cd apps/console && npm run build
uv run python scripts\export_openapi.py
```

As of the current workspace state, those checks pass.

Next implementation phases:

- `10-production-foundation-and-console-wiring`: production foundation,
  Docker Compose, Postgres / Redis / MinIO wiring, durable repositories,
  durable Native write APIs, worker loop, generated Console SDK wiring,
  OpenAPI diff, and making real Console-to-backend integration the primary
  frontend path.
- `11-runtime-production-hardening`: production Runtime reliability, Redis
  queue semantics, lease reaper, fencing-token protection, pub/sub cancel,
  quota, queue partitioning, streaming replay/fan-out/backpressure, crash
  recovery, and horizontal worker scaling.
- `12-enterprise-ops-and-cloud-native`: enterprise operations, production
  Artifact Store, external observability exporters, backup/restore, webhook
  subscriptions, alerting/incidents, Helm/K8s, and sandbox/container-pool
  boundaries.

The next concrete implementation step is phase 10. Kafka, Temporal,
multi-region deployment, leaderless reapers, and open-ended custom backend
routes remain later optional work, not part of the immediate production
foundation.

## LangChain Ecosystem Version Policy

DimooRun starts from the LangChain 1.x / LangGraph 1.x ecosystem line and uses a
fixed tested baseline for reproducible implementation and production runs:

```text
langchain      1.3.1
langchain-core 1.4.0
langgraph      1.2.1
deepagents     0.6.3
langsmith      0.8.5
```

Version upgrades are explicit maintenance work: update the matrix, update the
lockfile, and run adapter conformance tests before accepting the upgrade.

## Repository Layout

```text
.
├── apps/
│   ├── server/         # FastAPI Runtime API scaffold
│   ├── worker/         # Worker process entrypoint scaffold
│   └── console/        # Vue Console scaffold
├── deploy/             # Deployment assets placeholder
├── examples/
│   ├── compatibility/  # LangGraph Compatibility API examples
│   └── langgraph/      # LangGraph Agent examples
├── execution_plans/    # Chinese implementation plans mapped to DESIGN_SPEC.md
├── migrations/         # Alembic migrations for platform metadata tables
├── openapi/            # Generated OpenAPI artifacts
├── tests/              # Backend API, domain, persistence, and server tests
├── DESIGN_SPEC.md      # Architecture and product design specification
├── README.md           # Project overview
├── main.py             # Minimal Python entrypoint placeholder
├── pyproject.toml      # Python project metadata and tool config
└── uv.lock             # uv lockfile
```

## Development Prerequisites

- Python 3.11+
- uv

Run the placeholder entrypoint:

```bash
uv run python main.py
```

Run backend scaffold tests:

```bash
uv run pytest -q
```

Run adapter contract tests:

```bash
uv run pytest tests/adapters -q
```

Run backend quality checks:

```bash
uv run ruff check .
uv run mypy apps/server tests scripts
```

Run database migrations:

```bash
uv run alembic upgrade head
```

Export OpenAPI:

```bash
uv run python scripts/export_openapi.py
```

Run the Worker entrypoint:

```bash
uv run python apps/worker/dimoo_run_worker/main.py
```

Build the Console:

```bash
cd apps/console
npm run test
npm run build
```

Run the 09 CLI / Compatibility / Migration checks:

```bash
uv run pytest tests/cli tests/compat tests/migration tests/sdk -q
```

## Design Principle

DimooRun should absorb useful ideas from LangGraph Platform, Aegra, Dify,
Langfuse, Phoenix, Haystack, Letta, and other projects without changing its
core identity:

```text
Adapter-first enterprise runtime and control plane for production AI agents.
```
