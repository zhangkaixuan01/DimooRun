# Phase 0H Evidence Checklist

Phase 0H covers the Published Surface, Ingress, and Agent Gateway workflow.
The feature implementation is in place. As of 2026-06-09, local real-terminal
live-browser proof has been collected, but the phase remains `partial` until
the remaining hosted execution evidence is collected.

## What Is Already Proven

- Local backend API coverage:
  `uv run pytest tests/api/test_published_surface_workflows.py -q`
- Local mocked browser coverage:
  `npm run test:e2e:0h`
- Local live-backend launcher self-check:
  `node scripts/start-live-backend.mjs --check`
- Local real-terminal live-browser pass:
  `npm run cleanup:e2e:live`
  `npm run test:e2e:live:local`
- Local live smoke report verification logic:
  `npm run verify:e2e:live-report`

These checks prove the 0H APIs, mocked browser workflow, launcher guardrails,
live smoke log validation, and one clean local live browser pass against the
real backend/runtime path. They do not yet prove hosted CI/browser evidence.

## Remaining External Evidence

1. Hosted CI artifact proving the default Playwright-managed Chromium cache
   path:
   `npx playwright install --with-deps chromium`
   `npm run test:e2e:0h`
2. Hosted evidence that the governed browser flow is exercised end to end with
   the default Playwright-managed browser path:
   route test, request-log drilldown, traffic split, live ingress, revoke, and
   rollback.

## Latest Local Live Result

Date checked: 2026-06-09

Status: `local-live-pass-real-terminal`

Observed outcome:

- `npm run test:e2e:live:local` completed in a normal Windows terminal.
- The live smoke reached route test, request-log drilldown, traffic split,
  live ingress, revoke, rollback, and post-rollback ingress acceptance.
- `npm run verify:e2e:live-report` accepted
  `%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`.
- Cleanup completed after the verified pass.

## Local Operator Notes

- Working directory for the browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`
- Live smoke log path:
  `%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`

## Acceptance For Closing 0H

0H can move beyond `partial` only when all of the following are true:

1. The bounded 0H backend API suite stays green.
2. The mocked 0H browser suite stays green.
3. The live-browser 0H wrapper finishes cleanly in a real terminal and
   `npm run verify:e2e:live-report` accepts the resulting log.
4. A hosted CI run publishes the dedicated `console-playwright-0h-report`
   artifact after using the default Playwright-managed Chromium cache.
