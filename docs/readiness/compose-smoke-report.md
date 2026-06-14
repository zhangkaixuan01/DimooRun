# Compose Smoke Report

This report records the current local evidence for the Docker Compose runtime smoke path. It is not a pass report.

## Command

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

Supporting environment checks:

Working directory: repository root.

```bash
docker compose version
docker version
```

## Result

Status: `blocked-by-local-docker-daemon`

Date checked: 2026-06-13

`docker compose version` succeeds with Docker Compose `v5.1.3`, but `docker version` cannot connect to the Docker Desktop Linux engine. The live Compose smoke script now auto-prepares `.env` from `.env.example`, waits for health checks, and probes runtime backup/restore dry-runs. The Compose console image now also builds the Vue bundle and serves it through the repo static server with an explicit HTTP healthcheck instead of relying on the Vite dev server. This environment still cannot prove that the server, worker, Console, Postgres, Redis, and MinIO containers start successfully because the Docker daemon itself is unavailable.

Latest hosted observation:

- `integration.yml` run `27475315682`
- Date checked: `2026-06-14`
- Commit SHA: `2f1fbc1d4deacbb514b3dfbf90ad1662086fc6e2`
- Hosted result: Compose smoke job passed with
  `compose-config`, `compose-up`, `server-health`, `console-health`,
  `postgres-ready`, `minio-ready`, `backup-restore-dry-run`, and `compose-ps`
  in the job log.
- Hosted artifact published: `compose-runtime-smoke`

This hosted run is useful evidence that the committed integration contract
worked on GitHub-hosted runners for that SHA. It is not yet the final closeout
for the current worktree because the current uncommitted workflow/docs chain
expects the matching `compose-runtime-smoke-index` artifact to be part of the
evidence set.

## Evidence

Observed Docker daemon failure:

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

Observed live smoke failure:

```text
Compose runtime smoke failed: Command '['docker', 'compose', 'up', '--build', '--detach', '--wait']' returned non-zero exit status 1.
unable to get image 'dimoorun-migrator': failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
Compose runtime smoke failed: teardown failed: Command '['docker', 'compose', 'down', '--remove-orphans', '--volumes']' returned non-zero exit status 1.
```

Static contract evidence still passes:

Working directory: repository root.

```bash
uv run python scripts/compose_smoke.py
```

Expected static output:

```text
Compose smoke contract passed for services: migrator, server, worker, console, postgres, redis, minio
```

## Next Action

Run the live smoke in an environment where the Docker daemon is available:

Working directory: repository root.

```bash
uv run python scripts/compose_runtime_smoke.py
```

If it passes, update this report and `scorecard.md` with the current command output. If it fails after Docker is reachable, keep the failure here and investigate the first failing service from `docker compose ps` and service logs.

Hosted integration evidence now has stable artifact names for citation:

- diagnostics artifact: `compose-runtime-smoke`
- evidence index artifact: `compose-runtime-smoke-index`

The evidence index points back to `integration.yml`, the hosted smoke command,
and the expected diagnostic files `compose-ps.txt` plus `compose-logs.txt`.

The parallel Kubernetes / KinD contract is tracked separately in
[KinD Smoke Report](kind-smoke-report.md).

## Hosted CI Backfill Template

Fill this section when a hosted integration run is available:

- Hosted run id: `<run-id>`
- Branch/ref: `<branch-or-tag>`
- Date checked: `<yyyy-mm-dd>`
- Published artifacts:
  - `compose-runtime-smoke`
  - `compose-runtime-smoke-index`
- Outcome summary:
  - `<pass-or-fail summary>`
  - `<key container/runtime evidence>`
  - `<remaining follow-up if not fully closed>`

## Scorecard Rows To Update

When hosted integration proof is available, update these rows in
`docs/readiness/scorecard.md` with the same hosted run id and artifact names:

- `Phase 1: Production Truth Baseline`
- `Phase 10: Deployment And Operations Hardening`
- `Docker Compose smoke passes from a clean checkout.`
- `Milestone C: External GA`

