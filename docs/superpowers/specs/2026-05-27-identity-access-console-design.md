# Identity and Access Console Design

## Context

DimooRun is an enterprise control plane for agent runtime, deployment, governance, audit, and operations. Identity and access are not only login concerns. They define who can operate the console, which tenant/project/environment a request can touch, and which machine identities can call Native, Compatibility, Runtime, Deployment, Tool, Secret, and Admin APIs.

The current console has separate menu entries for tenants, projects, environments, operators, roles, permissions, service accounts, and API keys. Several of these entries are wired through a generic CRUD page. That makes the feature technically reachable but does not express the domain clearly enough for production operation.

This design consolidates the identity surface into four productized areas:

- Organization Scope
- Operators
- Roles and Permissions
- Machine Identity

## Product Model

### Human vs Machine Identity

DimooRun has two actor families:

- Operator: a human who signs in to the Console.
- Service Account: a machine identity used by CI/CD, external systems, Webhooks, MCP servers, Workers, automation scripts, and enterprise integrations.

Operators authenticate through console sessions. Service accounts authenticate through API keys. Both actor families use the same `resource:action` permission model and must be constrained by tenant/project/environment scope.

### Scope Hierarchy

Tenant, project, and environment define resource boundaries:

```text
Tenant
  -> Project
      -> Environment
```

Tenant is the top-level isolation boundary. Project is a tenant-owned workspace or business domain. Environment is the runtime lane for deployment and execution, such as `local`, `dev`, `staging`, or `prod`.

All console requests and API-key requests must resolve to an allowed scope before reaching business logic.

### Permission Model

Permissions are platform-defined capability codes in the `resource:action` format. Examples:

- `identity:operator:read`
- `identity:operator:write`
- `identity:scope:write`
- `agent:read`
- `agent:deploy`
- `run:cancel`
- `secret:read`
- `tool:call`
- `trace:read_prompt`

Permissions are not menu names. The frontend may hide or disable UI based on permissions, but backend checks are authoritative.

## Information Architecture

Replace the current eight separate identity entries with four entries:

```text
Identity and Access
  - Organization Scope
  - Operators
  - Roles and Permissions
  - Machine Identity
```

The previous objects still exist, but they are grouped by how administrators think about the work.

## Organization Scope

Organization Scope manages tenants, projects, and environments in one page.

### Page Structure

Use tabs:

- Tenants
- Projects
- Environments

The page should support cross-filtering:

- Selecting a tenant filters projects.
- Selecting a project filters environments.
- Environment creation requires a tenant and project.

### Tenant

Tenant is the enterprise/customer/business-unit boundary.

Required fields:

- name
- slug
- status
- description

Useful read-only summary:

- project count
- operator count
- service account count
- created_at
- updated_at

Actions:

- create
- edit
- enable
- disable
- archive

Disabling a tenant must prevent new console and API-key operations inside that tenant scope. Historical records remain visible to authorized operators.

### Project

Project is a workspace under a tenant.

Required fields:

- tenant_id
- name
- slug
- status
- description

Useful read-only summary:

- environment count
- active deployment count
- service account count
- recent run count

Actions:

- create under tenant
- edit
- enable
- disable
- archive

Disabling a project must prevent new runtime and admin writes inside that project scope.

### Environment

Environment is the runtime lane under a tenant/project pair.

Required fields:

- tenant_id
- project_id
- name
- environment code
- status
- is_production
- metadata

Actions:

- create under project
- edit
- enable
- disable
- archive

Production environments must trigger stronger confirmation for dangerous operations such as deployment stop, key creation with high-risk scopes, secret access, and restore operations.

## Operators

Operators are humans who can sign in to the Console.

### Page Structure

Use a dedicated Operators page:

- Operator table
- Create/edit global right-side drawer
- Operator details panel or route

### Operator Fields

Core fields:

- email
- name
- status
- roles
- allowed scopes
- optional direct permissions
- last_login_at
- password_changed_at

Allowed scopes are explicit:

```json
{
  "tenant_id": "tenant_1",
  "project_id": "project_1",
  "environment": "prod"
}
```

Wildcard scope may be supported for platform admins, but it should be visually obvious in the UI.

### Operator Actions

Create:

- name
- email
- initial password
- roles
- allowed scopes

Edit:

- name
- status
- roles
- allowed scopes
- optional direct permissions

Security actions:

- reset password
- revoke all sessions
- disable operator
- enable operator

Disabling an operator must revoke active sessions. Password reset and password change must also revoke existing sessions.

### Effective Permissions

Operator details should show effective permissions resolved from:

- roles
- role permissions
- optional direct permissions

The direct permission path is an exception mechanism. The primary assignment path is through roles.

## Roles and Permissions

Roles and Permissions manage reusable authorization policy.

### Page Structure

Use one page with tabs:

- Roles
- Permission Catalog

Roles define permission bundles. Permissions are platform-defined capability codes.

### Roles

Role fields:

- name
- description
- status
- permission set
- created_at
- updated_at

Actions:

- create role
- edit role
- duplicate role
- disable role
- enable role
- assign permissions through matrix

Disabling a role removes its permissions from operators and service accounts immediately during authorization checks.

### Permission Matrix

Role detail should present a matrix grouped by product domain:

- Identity
- Runtime
- Deployment
- Governance
- Observability
- Ops
- Settings

Each permission row should show:

- code
- label
- description
- risk level
- read/write/destructive classification

High-risk permissions include examples such as:

- `secret:read`
- `tool:call`
- `run:read_input`
- `trace:read_prompt`
- `backup:restore`
- `deployment:stop`

Assigning high-risk permissions should require a stronger confirmation.

### Permission Catalog

The permission catalog is platform-defined and mostly read-only.

Administrators should not freely create arbitrary permission codes in normal UI. The catalog can expose:

- code
- module
- action
- description
- risk level
- status

Custom permission creation can be added later as an extension feature, but it is not part of this production console pass.

## Machine Identity

Machine Identity manages service accounts and their API keys.

### Purpose

Service accounts represent non-human callers:

- CI/CD deployers
- external integrations
- scheduled automation
- Webhook senders or receivers
- MCP servers
- Workers
- enterprise integration jobs

API keys are credentials owned by service accounts. An API key should not be treated as an independent identity.

### Page Structure

Use one Machine Identity page:

- Service account list
- Service account details
- API keys nested under the selected service account
- Create/edit drawers for service accounts
- Create-key modal or drawer with one-time secret display

The primary object is the service account. API keys are managed from service account detail.

### Service Account Fields

Core fields:

- tenant_id
- project_id nullable
- name
- description
- status
- roles
- permissions
- allowed scopes
- expires_at nullable
- rotation_policy
- last_used_at
- created_by
- created_at
- updated_at

Rules:

- Service account permissions must be explicitly granted.
- A service account must not inherit the creator's full permissions.
- High-risk permissions require confirmation and later can require approval.
- Disabling a service account must invalidate all its active API keys.

### API Key Fields

Core fields:

- tenant_id
- project_id nullable
- service_account_id
- name
- key_prefix
- key_hash
- scopes
- status
- last_used_at
- expires_at
- rotation_policy
- created_by
- created_at

Rules:

- Raw API key is shown only once after creation.
- Backend stores only a hash.
- API key scopes must be a subset of the owning service account permissions.
- Project-scoped API keys cannot access other projects.
- Disabled or expired API keys must be rejected by Native, Runtime, Admin, and Compatibility APIs.
- All API key calls must write audit facts with `actor_type=service_account`.

### API Key Lifecycle

Supported actions:

- create key
- copy one-time key secret
- disable key
- rotate key
- set expiration
- view last used time
- view key prefix and key id

The UI must never show the full raw key after creation.

## Backend API Shape

The backend should expose product-specific endpoints while keeping compatibility aliases where needed.

Recommended new routes:

```text
GET    /v1/identity/scopes/tenants
POST   /v1/identity/scopes/tenants
PATCH  /v1/identity/scopes/tenants/{tenant_id}

GET    /v1/identity/scopes/projects
POST   /v1/identity/scopes/projects
PATCH  /v1/identity/scopes/projects/{project_id}

GET    /v1/identity/scopes/environments
POST   /v1/identity/scopes/environments
PATCH  /v1/identity/scopes/environments/{environment_id}

GET    /v1/identity/operators
POST   /v1/identity/operators
PATCH  /v1/identity/operators/{operator_id}
POST   /v1/identity/operators/{operator_id}/reset-password
POST   /v1/identity/operators/{operator_id}/revoke-sessions

GET    /v1/identity/roles
POST   /v1/identity/roles
PATCH  /v1/identity/roles/{role_id}
PUT    /v1/identity/roles/{role_id}/permissions

GET    /v1/identity/permissions

GET    /v1/identity/service-accounts
POST   /v1/identity/service-accounts
PATCH  /v1/identity/service-accounts/{service_account_id}
POST   /v1/identity/service-accounts/{service_account_id}/disable
POST   /v1/identity/service-accounts/{service_account_id}/enable

GET    /v1/identity/service-accounts/{service_account_id}/api-keys
POST   /v1/identity/service-accounts/{service_account_id}/api-keys
POST   /v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/disable
POST   /v1/identity/service-accounts/{service_account_id}/api-keys/{key_id}/rotate
```

Existing routes such as `/v1/service-accounts` and `/v1/api-keys` may remain as compatibility aliases until the console is moved fully to the new structure.

## Frontend Pages

Create or refactor toward these pages:

- `IdentityScopePage.vue`
- `OperatorsPage.vue`
- `RolePermissionPage.vue`
- `MachineIdentityPage.vue`

Shared UI patterns:

- global right-side drawer for create/edit
- confirmation dialog for destructive/high-risk actions
- one-time secret display component
- permission matrix component
- scope picker component
- role picker component
- API state component for loading/error/empty states

## Authorization Requirements

Read permissions:

- `identity:scope:read`
- `identity:operator:read`
- `identity:role:read`
- `identity:permission:read`
- `service_account:read`
- `api_key:read`

Write permissions:

- `identity:scope:write`
- `identity:operator:write`
- `identity:role:write`
- `service_account:write`
- `api_key:write`

Dangerous actions:

- `identity:operator:disable`
- `identity:operator:reset_password`
- `service_account:disable`
- `api_key:disable`
- `api_key:rotate`

The backend must enforce these permissions. Frontend gating is only a usability layer.

## Audit Requirements

Audit every identity mutation:

- tenant/project/environment create, update, disable, archive
- operator create, update, disable, password reset, session revoke
- role create, update, disable, permission update
- service account create, update, disable, enable
- API key create, disable, rotate

Audit records must include:

- actor_type
- actor_id
- tenant_id
- project_id
- environment when relevant
- action
- resource_type
- resource_id
- request_id
- result
- timestamp

API-key authenticated calls must identify `actor_type=service_account`.

## Error Handling

Stable error codes:

- `scope_not_allowed`
- `permission_denied`
- `tenant_disabled`
- `project_disabled`
- `environment_disabled`
- `operator_disabled`
- `role_disabled`
- `service_account_disabled`
- `api_key_disabled`
- `api_key_expired`
- `api_key_scope_exceeds_owner`
- `api_key_secret_unavailable`
- `resource_conflict`
- `resource_not_found`

Frontend should render error messages from stable codes, not by parsing backend message text.

## Testing

Backend tests:

- tenant/project/environment hierarchy filtering
- disabled scope rejects writes
- operator creation and session revocation
- role permission matrix persistence
- effective permission resolution
- service account explicit permissions
- API key scopes cannot exceed service account permissions
- API key one-time raw secret behavior
- disabled service account invalidates keys
- disabled/expired key rejects Runtime/Admin/Compatibility APIs
- audit actor_type is correct for operator and service account calls

Frontend tests:

- four identity menu entries exist
- organization tabs filter correctly
- operator drawer requires roles and scopes
- role permission matrix toggles and saves permissions
- machine identity page creates service account first, then nested API key
- API key raw secret is shown once and not persisted in local state after closing
- permission-gated buttons are hidden or disabled

## Design Decisions

- Merge eight identity menu entries into four product areas.
- Keep operators and service accounts separate because human login and machine API access have different lifecycle and security requirements.
- Treat service account as the identity and API key as its credential.
- Make permission catalog platform-defined and mostly read-only.
- Keep backend authorization authoritative; frontend only reflects capability.
- Keep compatibility routes temporarily to avoid breaking existing console and tests during migration.

## Self-Review

- Service Account and API Key positioning matches `DESIGN_SPEC.md` and execution plan 06.
- API Key is nested under Service Account, not treated as a standalone identity.
- The design keeps tenant/project/environment as scope, not as login configuration.
- Permission model remains `resource:action` and does not rely on menu names.
- The scope is focused on identity and access console productization, not unrelated runtime pages.
