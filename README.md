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

## Identity And ID Model

DimooRun treats a new database as the source of truth. Internal managed
resources use numeric auto-increment IDs from day one: tenants, projects,
environments, operators, roles, permissions, service accounts, API keys, agents,
versions, deployments, runs, attempts, tasks, events, policies, audit logs, and
other platform metadata all use `BIGINT` primary / foreign keys.

String identifiers are reserved for protocol and external boundaries such as
`thread_id`, `assistant_id`, `checkpoint_id`, `request_id`, `event_id`,
`trace_id`, `worker_id`, idempotency keys, key prefixes / hashes, object storage
URIs, slugs, and configuration references. Console and Admin APIs serialize
scope headers as HTTP strings, but their semantic value is a numeric ID.

## Current Status

This repository has completed implementation phases `01` through `13` and is
test-green for the current local verification baseline. It now includes the MVP
runtime, production-foundation wiring, runtime hardening, and enterprise
operations / cloud-native deployment foundations, plus Console live-backend
wiring and admin surface coverage. Real Docker Compose and Helm smoke runs still
need to be executed in an environment with Docker and Helm available before
treating those deployment paths as fully environment-verified.

The primary artifact is [DESIGN_SPEC.md](docs/DESIGN_SPEC.md), which describes the
target architecture, runtime model, compatibility strategy, MVP scope, and
roadmap. The cleanup note
[IMPLEMENTATION_UPDATE_2026-05-30.md](docs/IMPLEMENTATION_UPDATE_2026-05-30.md)
summarizes the numeric-ID, identity, Console, and Docker dev changes from the
latest structural pass.

Product documentation entry points:

- [Documentation home](docs/README.md)
- [Product overview](docs/PRODUCT_OVERVIEW.md)
- [Getting started](docs/GETTING_STARTED.md)
- [Quickstart](docs/QUICKSTART.md)
- [Current maturity](docs/CURRENT_MATURITY.md)
- [Production readiness scorecard](docs/PRODUCTION_READINESS_SCORECARD.md)

Implemented phase slices:

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
  Run Detail, Tasks, Events, Debug / Replay, Human Tasks, Policies, Machine
  Identities, Settings, Chinese / English switching, light / dark theme switching, high-risk
  operation confirmation, ECharts runtime trends, GSAP-scoped page motion, and
  frontend contract tests. Phase 13 replaces the old mock-first page data path
  with live API as the default and keeps mock data behind explicit demo mode.
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
- `10-production-foundation-and-console-wiring`: `.env.example`, Docker Compose
  and Dockerfile assets for server / worker / console / Postgres / Redis /
  MinIO, env-driven server CORS and SQLAlchemy Native runtime selection,
  CLI wrappers for `dev` / `up` / `down` / `logs` / `worker`, a minimal worker
  loop entrypoint, durable repository methods for AgentVersion / Deployment /
  Run / Task / Event / AuditLog, SQLAlchemy-backed Native Agents / Versions /
  Runs / Tasks API tests, durable `POST /v1/deployments`, OpenAPI diff checking,
  and a typed Console Native API client boundary.
  The local Compose stack uses `postgres:16-alpine`, `redis:8-alpine`, and
  `minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1`.
- `11-runtime-production-hardening`: Redis queue semantics, durable
  lease / heartbeat / reaper behavior, fencing-token protection across worker
  writes, RunAttempt lifecycle hardening, pub/sub cancel, quota and partition
  metadata, stream replay / fan-out / backpressure, crash recovery, and worker
  horizontal-scaling boundaries.
- `12-enterprise-ops-and-cloud-native`: production Artifact Store boundaries
  for local and S3/MinIO-compatible object storage, external observability
  exporters, BackupPlan / RestoreJob dry-run validation with scope checks,
  Event Webhook Subscription with minute-window rate limiting, Notification /
  Alerting incident lifecycle, Helm / K8s manifests, Helm smoke validation, and
  Sandbox / Container Pool enterprise boundaries.
- `13-console-real-backend-and-admin-ui`: Console default data mode now uses the
  live DimooRun API when `VITE_DIMOORUN_API_BASE_URL` is set, shows an explicit
  offline state when it is not configured, and only uses mock data when
  `VITE_DIMOORUN_DEMO_MODE=true`. Runtime pages now load agents, deployments,
  runs, tasks, run detail, run events, human tasks, and admin collections
  through the API client. Deployment pause / resume / restart and Human Task
  approve / reject call backend actions. Identity, Governance, Observability,
  Enterprise Ops, Compatibility, and Settings navigation now exposes the
  relevant backend admin surfaces. Tenant, project, and environment are now
  first-class Identity resources with Console CRUD pages; API requests use the
  logged-in operator's selected scope instead of frontend env constants. Scope
  resources are backed by SQLAlchemy models and Alembic migrations instead of
  the in-memory admin collection path. Machine identity management is centered
  on Service Accounts, with API keys managed as nested credentials that can be
  created, disabled, re-enabled, and deleted from the selected service account.
  Generic `/v1/service-accounts` and `/v1/api-keys` admin collection paths were
  removed from the Console path; old Console routes redirect to Machine
  Identities.

Recent structural cleanup:

- All internal table IDs and code-facing resource IDs have been normalized to
  numeric IDs for a clean new-database schema.
- Tenant / Project / Environment bootstrap still uses slugs for lookup, but the
  stored IDs are numeric and are what the Console sends after scope selection.
- Frontend relationship columns prefer names over raw IDs where the API provides
  enough data, and timestamp display uses local `yyyy-MM-dd HH:mm:ss`.
- Docker Compose dev enables filesystem polling for frontend hot reload in the
  dev override only; production compose files are unaffected.

Current verification baseline:

```text
uv run pytest -q
uv run ruff check apps tests packages\sdk-python scripts
uv run mypy apps/server tests scripts
uv run python scripts\helm_smoke.py
uv run python scripts\compose_smoke.py
uv run python scripts\compose_runtime_smoke.py
cd apps/console && npm run test
cd apps/console && npm run build
uv run python scripts\export_openapi.py
uv run python scripts\check_openapi_diff.py
```

Current local verification for phase 13 passes with `296 passed`, ruff, full
mypy, Console test, and Console production build. Kafka, Temporal, multi-region deployment,
leaderless reapers, and open-ended custom backend routes remain later optional
work, not part of the completed phase-13 foundation.

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
│   ├── server/         # FastAPI Runtime API and enterprise services
│   ├── worker/         # Worker process entrypoint and runtime loop
│   └── console/        # Vue Runtime Control Plane Console
├── deploy/             # Docker and Helm deployment assets
├── examples/
│   ├── compatibility/  # LangGraph Compatibility API examples
│   └── langgraph/      # LangGraph Agent examples
├── execution_plans/    # Chinese implementation plans mapped to DESIGN_SPEC.md
├── migrations/         # Alembic migrations for platform metadata tables
├── openapi/            # Generated OpenAPI artifacts
├── tests/              # Backend API, domain, persistence, and server tests
├── DESIGN_SPEC.md      # Architecture and product design specification
├── README.md           # Project overview
├── main.py             # Minimal Python entrypoint
├── pyproject.toml      # Python project metadata and tool config
└── uv.lock             # uv lockfile
```

## Development Prerequisites

- Python 3.11+
- Node.js 20+
- uv

Run the local backend API:

```bash
cp .env.example .env
uv run uvicorn dimoo_run.server:app --reload --host 127.0.0.1 --port 8000
```

Run the Console against that backend:

```bash
cd apps/console
npm run dev
```

Run the Docker Compose stack:

Working directory: repository root.

```bash
uv run python scripts/compose_smoke.py
```

This validates the Compose contract for server, worker, console, Postgres,
Redis, and MinIO without starting containers.

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

This starts the Compose stack, waits for the server `/healthz` endpoint and the
Console root page, prints `docker compose ps`, and tears the stack down.

Working directory: repository root.

```bash
docker compose up --build
```

Run the Docker Compose development stack with source mounts and reload:

Working directory: repository root.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

After the first build, ordinary backend and Console source edits are picked up
through bind mounts. Rebuild only when Python or Node dependencies change, or
when Dockerfile/build inputs change.

Both backend and Console read the repository-root `.env`. Vite is configured
with `envDir: "../.."`, so `apps/console/.env` is intentionally not used.
`DIMOORUN_DEV_API_KEY` is accepted by API requests only when
`DIMOORUN_RUNTIME_MODE=dev`; the browser Console uses operator sessions after
login and does not read a frontend API key.
Console operator sessions require Redis through `REDIS_URL`; login fails
closed when the session store is unavailable. The database stores only session
token hashes, while Redis stores the active session payload with TTL.

Default local Console login:

```text
email: admin@local.dimoorun
password: admin12345
```

The Console is an operator/admin surface. It does not provide public
self-registration. Operators are created from Identity / Operators after a
platform admin signs in. Service accounts and API keys remain the machine-to-
machine path.

Run the minimal Python entrypoint:

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

Run the first phase 10 production-foundation checks:

```bash
uv run pytest tests/production_foundation tests/server tests/cli -q
uv run python scripts/check_openapi_diff.py
dimoorun up --dry-run
dimoorun dev --dry-run
```

The Compose assets are present and covered by local tests. A real Docker
Compose smoke run should still be executed in an environment with Docker,
Postgres, Redis, and MinIO available before treating the stack as deployable.

## Design Principle

DimooRun should absorb useful ideas from LangGraph Platform, Aegra, Dify,
Langfuse, Phoenix, Haystack, Letta, and other projects without changing its
core identity:

```text
Adapter-first enterprise runtime and control plane for production AI agents.
```
