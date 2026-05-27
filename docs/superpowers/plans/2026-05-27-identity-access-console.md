# Identity Access Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Productize the Identity and Access console into Organization Scope, Operators, Roles and Permissions, and Machine Identity.

**Architecture:** Keep existing auth/session work intact. Add focused backend endpoints for nested service account API keys and reuse existing DB-backed scope/operator/role/permission paths. Replace the identity sidebar entries with four product pages that call real APIs through the existing console client.

**Tech Stack:** FastAPI, existing APIKeyAuthenticator and ServiceAccountRegistry, Vue 3, Pinia, existing console API client, pytest, npm console contract tests.

---

## Files

- Modify: `apps/server/dimoo_run/api/admin/router.py` for machine identity endpoints.
- Modify: `apps/server/dimoo_run/security/api_keys.py` to expose safe key metadata and disable/list helpers.
- Modify: `apps/server/dimoo_run/identity/service_accounts.py` to expose list/update helpers.
- Modify: `tests/api/test_console_auth_api.py` or `tests/api/test_admin_api.py` for machine identity API behavior.
- Create: `apps/console/src/pages/identity/IdentityScopePage.vue`.
- Create: `apps/console/src/pages/identity/RolePermissionPage.vue`.
- Create: `apps/console/src/pages/identity/MachineIdentityPage.vue`.
- Modify: `apps/console/src/pages/identity/OperatorsPage.vue` only as needed for route consistency.
- Modify: `apps/console/src/router/index.ts` to use four identity routes.
- Modify: `apps/console/src/layouts/AppShell.vue` to show four identity navigation entries.
- Modify: `apps/console/src/i18n/messages.ts` for new labels.
- Modify: `apps/console/src/api/client.ts` if nested machine identity helpers are useful.

## Task 1: Backend Machine Identity API

- [x] Write failing pytest for nested service-account API key lifecycle.
- [x] Implement service account list/update helpers.
- [x] Implement API key list/disable helpers.
- [x] Add `/v1/identity/service-accounts` and nested `/api-keys` routes.
- [x] Verify API key scopes cannot exceed owning service account permissions.
- [x] Verify raw key is returned only at creation and not in list responses.

## Task 2: Identity Navigation and Product Pages

- [x] Add four route targets: `/identity/scopes`, `/identity/operators`, `/identity/roles-permissions`, `/identity/machine-identities`.
- [x] Update sidebar identity group to four entries.
- [x] Preserve redirects from old tenant/project/environment/roles/permissions/service-account/API-key routes.
- [x] Build Organization Scope page with tabs over tenants/projects/environments.
- [x] Build Roles and Permissions page with role creation drawer and a role permission matrix-style view.
- [x] Build Machine Identity page with service-account creation drawer, nested key list, key drawer, and one-time key display.

## Task 3: Verification

- [x] Run focused backend tests for admin and console auth.
- [x] Run full pytest.
- [x] Run ruff and mypy.
- [x] Run console build and console tests.
