# DimooRun

DimooRun is an adapter-first enterprise runtime platform for AI agents.

The project starts with LangGraph compatibility and is designed to expand to
LangChain Agents, DeepAgents, HTTP Agents, CrewAI, LlamaIndex, and other agent
frameworks through a stable adapter contract.

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

This repository is in the design and project-initialization stage.

The primary artifact is [DESIGN_SPEC.md](DESIGN_SPEC.md), which describes the
target architecture, runtime model, compatibility strategy, MVP scope, and
roadmap.

No production runtime implementation has been started yet.

## Repository Layout

```text
.
├── DESIGN_SPEC.md      # Architecture and product design specification
├── README.md           # Project overview
├── main.py             # Minimal Python entrypoint placeholder
├── pyproject.toml      # Python project metadata
├── uv.lock             # uv lockfile
└── .python-version     # Python version pin
```

## Development Prerequisites

- Python 3.11+
- uv

Run the placeholder entrypoint:

```bash
uv run python main.py
```

## Design Principle

DimooRun should absorb useful ideas from LangGraph Platform, Aegra, Dify,
Langfuse, Phoenix, Haystack, Letta, and other projects without changing its
core identity:

```text
Adapter-first enterprise runtime and control plane for production AI agents.
```
