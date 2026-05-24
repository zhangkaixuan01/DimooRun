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

This repository is in the early implementation stage.

The primary artifact is [DESIGN_SPEC.md](DESIGN_SPEC.md), which describes the
target architecture, runtime model, compatibility strategy, MVP scope, and
roadmap.

Completed implementation phases:

- `01-project-foundation`: FastAPI server scaffold, configuration models,
  Worker entrypoint, Vue Console scaffold, examples, OpenAPI output directory,
  and baseline tests.
- `02-domain-persistence-and-api`: SQLAlchemy domain models, Alembic migrations,
  repository boundaries, Native/Admin API contract skeletons, audit and soft
  delete semantics, idempotency records, placeholder metadata tables, and
  generated OpenAPI.

Next implementation phase:

- `03-agent-package-and-adapters`: Agent Package manifest, package loading,
  Adapter contract, LangGraphAdapter, and adapter conformance tests.

Production runtime execution, real task queues, real adapters, governance
decision logic, and full Console product screens are still planned work.

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
npm run build
```

## Design Principle

DimooRun should absorb useful ideas from LangGraph Platform, Aegra, Dify,
Langfuse, Phoenix, Haystack, Letta, and other projects without changing its
core identity:

```text
Adapter-first enterprise runtime and control plane for production AI agents.
```
