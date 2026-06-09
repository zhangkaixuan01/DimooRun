# Production Console Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace in-memory console identity with DB-backed operators/RBAC and Redis-backed production session validation.

**Architecture:** SQLAlchemy models and Alembic migrations provide durable identity state. A focused console identity service owns password hashing, token hashing, Redis session cache writes, DB fallback, revocation, scope checks, and permission checks. Frontend API handling clears invalid sessions globally and gates identity controls by permissions.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Redis Python client, Vue, Pinia, Vitest, pytest.

---

## Files

- Modify: `pyproject.toml` to add `redis`.
- Modify: `uv.lock` after dependency resolution.
- Modify: `apps/server/dimoo_run/domain/models.py` for console identity tables.
- Modify: `migrations/versions/0001_baseline.py` or add a new post-baseline revision for console identity schema changes.
- Add: `apps/server/dimoo_run/identity/console.py` for DB/Redis service.
- Modify: `apps/server/dimoo_run/api/dependencies.py` to delegate console identity to the service.
- Modify: `apps/server/dimoo_run/api/auth.py` for stronger lifecycle errors and permission use.
- Modify: `apps/server/dimoo_run/api/admin/router.py` so roles and permissions can use durable data.
- Modify: `apps/console/src/api/client.ts` for global 401 handling.
- Modify: `apps/console/src/stores/auth.ts` for auth invalidation.
- Modify: `tests/api/test_console_auth_api.py` for persistence, Redis, revocation, disabled users, and permission tests.
- Modify: `README.md` and `.env.example` for Redis/session startup notes.

## Task 1: Add Durable Identity Schema

- [ ] Add SQLAlchemy models for console operators, credentials, sessions, scopes, roles, permissions, and joins.
- [ ] Add Alembic migration with matching tables, unique constraints, and indexes.
- [ ] Run `uv run pytest tests/api/test_openapi_contract.py -q` to ensure model imports do not break the app.

## Task 2: Add Redis-Backed Console Identity Service

- [ ] Add Redis dependency and lock it.
- [ ] Implement `ConsoleIdentityService` with bootstrap, login, session lookup, logout, operator CRUD, password change, password reset, role/permission listing, and session revocation.
- [ ] Store only token hashes in DB and Redis keys.
- [ ] Fail closed when Redis is unavailable for login/session mutation.
- [ ] Keep DB fallback for `/auth/me` when Redis misses but is reachable.

## Task 3: Replace API In-Memory Helpers

- [ ] Keep the existing public helper function names in `api/dependencies.py`.
- [ ] Remove process-local `_console_operators` and `_console_sessions`.
- [ ] Delegate all console helper behavior to `ConsoleIdentityService`.
- [ ] Preserve service-account API key fallback.
- [ ] Enforce scope and permission checks through durable operator permissions.

## Task 4: Complete Frontend Session Handling

- [ ] Add a global unauthorized handler in `client.ts`.
- [ ] Clear Pinia/localStorage auth state on 401 session errors.
- [ ] Redirect to `/login?redirect=<current path>`.
- [ ] Gate identity write actions by `*` or identity write permissions.

## Task 5: Tests and Verification

- [ ] Extend backend tests for Redis-backed login, DB fallback, logout revocation, password-reset revocation, disabled operator denial, scope denial, permission denial, and API-key fallback.
- [ ] Extend frontend tests for 401 invalidation if existing test harness supports it.
- [ ] Run `uv run pytest -q`.
- [ ] Run `uv run ruff check apps tests packages\sdk-python scripts migrations`.
- [ ] Run `uv run mypy apps/server tests scripts`.
- [ ] Run `cd apps/console && npm run build`.
- [ ] Run `cd apps/console && npm run test`.
