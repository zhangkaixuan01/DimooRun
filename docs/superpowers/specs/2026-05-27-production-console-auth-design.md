# Production Console Identity and Access Design

## Context

DimooRun already has a console login API, a Pinia auth store, and identity management pages. The current backend identity path is not production grade because console operators, password hashes, and sessions are process-local in-memory state. A backend restart invalidates all users and loses session audit history. Roles and permissions are stored as strings on the operator object instead of normalized RBAC data.

The target is a real administrator platform identity system: operators log in with credentials, receive access tokens, APIs validate the token on every request, expired or revoked sessions are denied, and the frontend reacts consistently to login state and permissions.

## Scope

This design covers the console administrator identity surface:

- Operator login, logout, current-user lookup, and password change.
- DB-backed operators, credentials, sessions, role assignments, permission assignments, and allowed tenant/project/environment scopes.
- Redis-backed session cache with TTL and explicit revocation.
- Console API authorization using the same Bearer header already used by the frontend.
- Frontend login-state handling, global 401 handling, and permission-driven controls.
- Tests and docs needed to validate the production path.

This design does not replace service-account API keys for programmatic access. Console sessions and API keys remain two supported Bearer credential types.

## Architecture

PostgreSQL or the configured SQL database is the source of truth. Redis is the runtime session cache and revocation accelerator. The system must not rely on process memory for correctness.

The backend will introduce a console identity service behind the existing auth helper functions. Existing API route call sites should keep stable names where possible to reduce blast radius, but implementation moves out of ad hoc dictionaries and into repositories/services.

Request authentication order:

1. Extract `Authorization: Bearer <token>`.
2. If token looks like a console session token, validate it through Redis first.
3. On Redis miss, validate the token hash against the DB session table, then repopulate Redis if still active.
4. If it is not a valid console session, fall back to service-account API key authentication.
5. Enforce scope and permission checks against the resolved actor.

## Data Model

Add console-specific tables instead of overloading the existing generic `roles` and `permissions` tables:

- `console_operators`: id, email, name, status, created_at, updated_at, last_login_at.
- `console_operator_credentials`: operator_id, password_hash, password_changed_at, failed_login_count, locked_until.
- `console_operator_sessions`: id, operator_id, token_hash, created_at, last_used_at, expires_at, revoked_at, revoke_reason, ip_address, user_agent.
- `console_operator_allowed_scopes`: operator_id, tenant_id, project_id, environment.
- `console_roles`: id, name, description, status.
- `console_permissions`: id, code, resource, action, description.
- `console_operator_roles`: operator_id, role_id.
- `console_role_permissions`: role_id, permission_id.
- `console_operator_permissions`: optional direct operator permission grants for operational exceptions.

Public API responses keep the existing shape where practical:

- `roles` remains a list of role names.
- `permissions` remains a list of permission codes.
- `allowed_scopes` remains a list of `{ tenant_id, project_id, environment }`.

## Session and Token Design

Access tokens are opaque strings with the prefix `sess_`. The raw token is returned only once at login. The database stores only a SHA-256 token hash.

Redis stores session lookup entries keyed by token hash:

- Key: `console:session:<token_hash>`
- Value: JSON with session id, operator id, permissions, roles, allowed scopes, and expiry.
- TTL: aligned with `expires_at`.

Logout, password changes, operator disablement, and admin password reset revoke DB sessions and delete Redis keys. DB remains authoritative, so Redis loss only causes a DB fallback, not an auth bypass.

Default access-token lifetime is 12 hours and should be configurable with `DIMOORUN_CONSOLE_ACCESS_TOKEN_TTL_SECONDS`.

## Authorization Rules

An operator is allowed through only when all conditions hold:

- Operator status is `active`.
- Session exists, is not expired, and is not revoked.
- Requested tenant/project/environment matches one of the operator allowed scopes. A `*` value means wildcard.
- Required permission is present directly, via role, or via wildcard `*`.

Console admin APIs require `admin:read` for reads and more specific write permissions for mutating identity surfaces:

- `identity:operator:write`
- `identity:role:write`
- `identity:permission:write`
- `identity:scope:write`

The bootstrap admin receives `*` and can create the first durable identity records.

## Frontend Flow

The console frontend stores the access token and public operator profile in localStorage, as it does today.

Required behavior:

- Login calls `/v1/auth/login`, stores token and operator, initializes selected scope from allowed scopes.
- App startup calls `/v1/auth/me` when a token exists.
- Any API response with 401 auth/session errors clears auth state and redirects to `/login?redirect=<current route>`.
- Menus and buttons check the current operator permissions before showing destructive or write actions.
- Identity pages use right-side global drawers with explicit forms for create/update flows.

## Redis Dependency

Redis is a production dependency for console session validation. If the Python Redis client is not present, add it to project dependencies and lock files. In development, startup checks or clear server logs should make missing Redis obvious.

The implementation should still fail closed if Redis is unreachable during auth operations. Login should not silently create process-local sessions. Existing tests can use a fake Redis client or an isolated in-memory adapter at the service boundary, but production code paths must be written around the Redis interface.

## Error Handling

Auth errors use stable error codes:

- `invalid_credentials`
- `session_invalid`
- `session_expired`
- `session_revoked`
- `operator_disabled`
- `scope_not_allowed`
- `permission_denied`
- `redis_unavailable`

Frontend 401 handling should key off HTTP status plus these error codes. Backend logs should include timestamped request handling, but never log raw passwords or raw access tokens.

## Testing

Backend tests must cover:

- Bootstrap admin is persisted in DB.
- Login creates a DB session and Redis session entry.
- `/auth/me` works through Redis and through DB fallback.
- Logout revokes DB session and deletes Redis session entry.
- Expired or revoked sessions return 401.
- Disabled operators cannot authenticate and existing sessions stop working.
- Password change and admin reset revoke existing sessions.
- Scope mismatch returns 403.
- Missing permissions return 403.
- Service-account API key authentication still works.

Frontend tests must cover:

- Login stores token/operator and initializes scope.
- Hydration calls `/auth/me`.
- 401 clears auth and redirects to login.
- Permission-gated controls are hidden or disabled.

## Rollout

1. Add models, migration, and repositories.
2. Add Redis client/session store and identity service.
3. Replace in-memory console identity helpers with DB/Redis-backed implementations.
4. Update auth and identity routes for stronger permissions and lifecycle handling.
5. Update frontend global 401 and permission gates.
6. Update docs, generated OpenAPI, and tests.

## Self-Review

- No placeholder requirements remain.
- Redis is explicitly production-required, not optional for real deployments.
- DB remains source of truth, avoiding cache-only session state.
- Existing public API shapes are preserved where practical to keep frontend and tests stable.
- The design is scoped to console identity and does not rewrite unrelated runtime authentication.
