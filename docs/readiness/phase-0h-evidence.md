# Phase 0H Evidence Checklist

Phase 0H covers the Published Surface, Ingress, and Agent Gateway workflow.
The feature implementation and local proof are now sufficient to treat the
phase boundary as `complete`. Hosted CI/default-browser evidence and externally
hosted gateway execution remain useful later hardening evidence, but they are
no longer blockers for closing Phase 0H itself.

## What Is Already Proven

- Local backend API coverage:
  `uv run pytest -q tests/api/test_published_surface_workflows.py tests/production_foundation/test_ci_workflow.py`
- Local mocked browser coverage:
  `npm run test`
  `npm run build:e2e`
- Local live-backend launcher self-check:
  `node scripts/start-live-backend.mjs --check`
- Shared live-backend browser pass:
  `npm run test:e2e:live`
- Local live smoke report verification logic:
  `npm run verify:e2e:live-report`

These checks prove the 0H APIs, mocked browser workflow, launcher guardrails,
live smoke log validation, and one clean shared live browser pass against the
real backend/runtime path. Dedicated `npm run test:e2e:0h` and hosted browser
artifacts remain useful later evidence, but they are not required to close the
phase boundary once the shared live path is green and verified.

## Latest Local Live Result

Date checked: 2026-06-13

Status: `local-live-pass-verified`

Observed outcome:

- `npm run test:e2e:live` completed successfully against the shared live
  backend path.
- The live smoke reached route test, request-log drilldown, traffic split,
  live ingress, revoke, rollback, and post-rollback ingress acceptance.
- `npm run verify:e2e:live-report` accepted
  `%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`.

## Local Operator Notes

- Working directory for the browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`
- Live smoke log path:
  `%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`

## Acceptance For Closing 0H

0H is considered closed when all of the following are true:

1. The bounded 0H backend API suite stays green.
2. The Console contract/build path stays green.
3. The live-browser 0H wrapper finishes cleanly and
   `npm run verify:e2e:live-report` accepts the resulting log.

## Later Hardening Evidence

- Hosted CI publication of the dedicated `console-playwright-0h-report`
  artifact on the default Playwright-managed Chromium cache.
- Externally hosted gateway/runtime execution evidence beyond the local/shared
  live proof collected in this repository.
