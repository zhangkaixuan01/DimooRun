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

`docker compose version` succeeds with Docker Compose `v5.1.3`, but `docker version` cannot connect to the Docker Desktop Linux engine. The live Compose smoke script now auto-prepares `.env` from `.env.example`, waits for health checks, and probes runtime backup/restore dry-runs, but this environment still cannot prove that the server, worker, Console, Postgres, Redis, and MinIO containers start successfully.

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

