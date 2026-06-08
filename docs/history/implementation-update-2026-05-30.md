# Implementation Update 2026-05-30

This note records the cleanup that moved DimooRun to a clean new-database model:
internal resources use numeric auto-increment IDs from the beginning, with no
legacy string-ID compatibility layer.

## ID Model

- Internal managed resources use numeric `BIGINT` primary keys and foreign keys.
- Python code treats internal resource IDs as `int`; Console code treats them as
  `number`.
- This applies to tenants, projects, environments, operators, roles,
  permissions, service accounts, API keys, agents, agent versions, deployments,
  runs, run attempts, tasks, events, policies, audit logs, and platform metadata.
- String IDs remain only where the value is an external protocol field or
  infrastructure reference: `thread_id`, `assistant_id`, `request_id`,
  `event_id`, `trace_id`, `correlation_id`, `checkpoint_id`, `worker_id`,
  idempotency keys, key prefix / hash, object storage URI, slugs, names, and
  external configuration references.

## Backend

- SQLAlchemy models and Alembic migrations were normalized around numeric IDs.
- Runtime context, task backend, Run / Task / Deployment / Agent paths, Admin
  identity models, and policy resource references were aligned with numeric IDs.
- Tenant / Project / Environment bootstrap still looks up defaults by slug, then
  stores and returns numeric IDs.
- Admin scope resolution now keeps nonexistent requested numeric IDs as filters
  instead of broadening scope to `None`.
- Generic in-memory `/v1/service-accounts` and `/v1/api-keys` admin collection
  routes were removed from the active product path.
- Compatibility API still accepts LangGraph-style path values, but maps them to
  DimooRun numeric `Run.id` internally and requires a real project scope.

## Identity And Machine Identity

- Console machine identity management now treats Service Account as the identity
  and API Key as its nested credential.
- API keys can be created, disabled, enabled, and deleted under a selected
  service account.
- Disabled keys can be re-enabled only when their scopes remain a subset of the
  owning service account permissions.
- When service account permissions are reduced, keys with excessive scopes are
  disabled.
- API key plaintext is only returned at creation time.

## Console

- Console resource IDs were normalized to `number`.
- Selected tenant and project scope values are numeric IDs.
- Relationship columns prefer display names over raw IDs when the API provides
  the related resource data.
- Tenant, project, environment, service account, API key, and other status badges
  update immediately after enable / disable operations.
- Timestamp display uses local `yyyy-MM-dd HH:mm:ss` formatting.
- Old `/identity/service-accounts` and `/governance/api-keys` Console routes now
  redirect to Machine Identities.

## Docker Dev

- `docker-compose.dev.yml` enables `CHOKIDAR_USEPOLLING=true` and
  `WATCHPACK_POLLING=true` for frontend hot reload in Docker bind mounts.
- These polling settings are dev-override only and do not affect production
  Compose configuration.

## Verification

Focused verification after the cleanup:

```text
uv run python -m compileall apps/server/dimoo_run
uv run pytest tests/api/test_admin_api.py -q
uv run pytest tests/api/test_native_api.py -q
uv run pytest tests/compat/test_langgraph_compat_api.py -q
cd apps/console && npm run build
```

The full test tree still contains older historical examples in some unrelated
tests; the focused admin, native API, compatibility API, backend compile, and
Console build checks passed during this cleanup.
