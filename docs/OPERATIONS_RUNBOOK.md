# Operations Runbook

This runbook is the operator-facing baseline for local and pre-production
DimooRun environments. It is intentionally conservative: it explains what to
check, what evidence to capture, and where current product maturity still
requires human judgment.

## Scope

This runbook covers:

- local Compose evaluation environments
- pre-production deployment change checks
- runtime failure triage
- incident response entry points
- backup and restore dry-run validation

It does not claim hosted production SLO proof or complete managed-service
operations guidance.

## Before You Start

- Confirm the target tenant, project, and environment scope.
- Confirm whether you are acting through Console, CLI, or direct API calls.
- Record a request ID or incident/ticket reference before high-risk actions.
- Check [Current Maturity](readiness/current-maturity.md) and
  [Trust And Security](TRUST_AND_SECURITY.md) if you are about to make a safety
  claim.

## Local Operator Baseline

Working directory: repository root.

```bash
docker compose ps
docker compose logs server --tail 50
docker compose logs worker --tail 50
```

Confirm:

- server is accepting requests
- worker is leasing and completing tasks
- Console is reachable
- Redis, Postgres, and object store containers are up

## Runtime Health Checks

Check these first when the runtime looks unhealthy:

- deployment desired status and runtime status
- latest run attempt status
- ordered run events
- worker assignment and heartbeat age
- audit records for denied or approval-required actions

Working directory: repository root.

```bash
uv run dimoorun run watch --base-url http://127.0.0.1:8000 --api-key dev-local-key --tenant-id 1 --project-id 1 --run-id <RUN_ID> --show-events
```

## Run Failure Triage

Use this order:

1. Confirm whether the run failed, retried, stalled, or is waiting for approval.
2. Open the run detail page and inspect attempts, events, version, deployment,
   and output/error summary.
3. Compare worker logs with runtime events.
4. Decide whether replay, rollback, approval, or incident response is the next action.

Prefer replay when:

- the source run is terminal
- you need to compare behavior across versions or replay config
- the failure appears deterministic enough to reproduce safely

## Deployment Change Management

Before activation, promotion, rollback, pause, or restart:

- record the actor and audit reason
- inspect active runs and queued tasks
- inspect candidate version readiness
- capture rollback target if one exists

Do not treat a visible button as proof the workflow is safe. Use the backend
impact preview and audit evidence path.

## Incident And Recovery

Use the incident workflow when a run failure becomes an operational problem:

- acknowledge with an audit note
- link the affected run, task, and event where available
- record notification channels used
- resolve only with a concrete resolution summary

Current incident workflows are useful for operator evidence, but they are not a
full hosted on-call system.

## Backup And Restore

Prefer dry-run validation before any destructive action.

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

During validation, capture:

- scope used for the dry-run
- target list
- storage reference
- destructive confirmation text, if relevant

## Evidence To Capture

When escalating or handing off, include:

- request ID
- tenant/project/environment scope
- deployment ID and version ID
- run ID and task ID
- relevant audit action
- screenshots or logs only after redaction review

## Escalation Boundary

Escalate before proceeding when:

- policy denies an action you expected to allow
- approval is required for a high-risk action
- backup/restore validation indicates scope mismatch
- runtime status contradicts stored deployment intent
