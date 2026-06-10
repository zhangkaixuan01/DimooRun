# Phase 0K Evidence Checklist

Phase 0K covers the Identity, Role, Permission, Session, and Machine Identity
workflow. As of 2026-06-10, the backend workflow and Console identity pages are
locally proven with targeted browser evidence. This phase should still stay
`partial` until hosted CI publishes the dedicated browser artifact and the
default Playwright-managed Chromium path is proven externally.

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

## Remaining External Evidence

1. Hosted CI artifact proving the default Playwright-managed Chromium cache path
   for the dedicated 0K workflow:
   `npm run test:e2e:0k`
2. Hosted browser evidence that the identity workflow stays green for role diff,
   self-lockout blocking, session revoke, machine-key rotation, and detail-page
   drilldown.

## Latest Local Result

Date checked: 2026-06-10

Status: `local-targeted-browser-pass`

Observed outcome:

- Backend 0K workflow tests passed locally.
- Console contract tests, unit tests, and E2E build passed locally.
- The targeted Playwright identity workflow spec passed locally with the
  configured Chrome path.
- CI now has a dedicated `npm run test:e2e:0k` workflow path and
  `console-playwright-0k-report` artifact wiring.
- Local re-runs through `npm run test:e2e:0k` are not yet re-proven on this
  Windows machine because repeated Playwright runs left locked `.last-run.json`
  files under reused `test-results*` directories. That does not weaken the
  direct targeted browser proof above, but it means the local CI-style wrapper
  evidence is still weaker than 0I/0J.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`

## Acceptance For Closing 0K

0K can move beyond `partial` only when all of the following are true:

1. The bounded 0K backend identity workflow suites stay green.
2. The targeted identity-governance browser spec stays green.
3. Hosted CI publishes the dedicated 0K Playwright artifact using the default
   Playwright-managed Chromium cache path.
4. The dedicated `npm run test:e2e:0k` path is proven in a clean environment
   without stale Playwright output locks.
