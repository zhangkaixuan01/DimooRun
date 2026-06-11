# Phase 0K Evidence Checklist

Phase 0K covers the Identity, Role, Permission, Session, and Machine Identity
workflow. As of 2026-06-11, the backend workflow and Console identity pages are
locally proven with targeted browser evidence, and hosted CI has now published
the dedicated browser artifact for the default Playwright-managed Chromium
path.

## What Is Already Proven

- Local backend identity workflow coverage:
  `uv run pytest -q tests/api/test_identity_workflows.py tests/production_foundation/test_ci_workflow.py`
- Local backend lint coverage for the 0K implementation:
  `uv run ruff check apps/server/dimoo_run/api/admin/identity_workflows.py apps/server/dimoo_run/api/console/identity.py apps/server/dimoo_run/identity/permission_matrix.py tests/api/test_identity_workflows.py tests/production_foundation/test_ci_workflow.py`
- Local Console contract, unit, and build proof:
  `npm run test`
  `npm run test:unit`
  `npm run build:e2e`
- Local targeted browser workflow proof:
  `npx playwright test tests/e2e/identity-governance.spec.ts --project=chrome --output test-results-0k-local`

These checks prove:

- role permission matrix preview with grouped permissions, effective diff, and
  affected-operator impact;
- self-lockout warning and blocked apply path before role-governance permissions
  are removed from the current operator;
- operator access detail with roles, inherited permissions, active sessions,
  created API keys, and audit history;
- operator session revoke from the detail workflow; and
- service-account detail with dependent deployment/published-surface visibility,
  key rotation, forced expiry, and scope drift display.

## Hosted CI Proof

- Successful hosted CI run `27347574486` on `main` from 2026-06-11 published
  `console-playwright-0k-report`.
- The artifact was produced by the dedicated workflow path using the default
  Playwright-managed Chromium cache:
  `npm run test:e2e:0k`

## Latest Local Result

Date checked: 2026-06-10

Status: `local-targeted-browser-pass`

Observed outcome:

- Backend 0K workflow tests passed locally.
- Console contract tests, unit tests, and E2E build passed locally.
- The targeted Playwright identity workflow spec passed locally with the
  configured Chrome path.
- CI now has a dedicated `npm run test:e2e:0k` workflow path and the latest
  successful hosted run has published `console-playwright-0k-report`, proving
  the clean-environment wrapper path.
- Local re-runs through `npm run test:e2e:0k` on this Windows machine remain
  less convenient because repeated Playwright runs can leave locked
  `.last-run.json` files under reused `test-results*` directories, but that is
  no longer a phase-closure blocker now that hosted CI has proven the clean
  path.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`

## Closure Verdict

0K is now considered closed for this phase because all of the following are
true:

1. The bounded 0K backend identity workflow suites stay green.
2. The targeted identity-governance browser spec stays green.
3. Hosted CI has published the dedicated 0K Playwright artifact using the default
   Playwright-managed Chromium cache path.
4. The dedicated `npm run test:e2e:0k` path is proven in a clean environment
   without stale Playwright output locks.
