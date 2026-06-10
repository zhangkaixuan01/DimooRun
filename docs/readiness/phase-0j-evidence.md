# Phase 0J Evidence Checklist

Phase 0J covers the Worker, Agent Instance, and Capacity Operations workflow.
As of 2026-06-10, the backend and Console workflow are locally proven, including
the dedicated `npm run test:e2e:0j` wrapper. This phase should stay
conservative in readiness reporting until hosted CI publishes the default
Playwright artifact path for the 0J workflow.

## What Is Already Proven

- Local backend worker/capacity workflow coverage:
  `uv run pytest -q tests/api/test_worker_capacity_console.py tests/api/test_console_aggregate_api.py`
- Local backend lint coverage for the 0J implementation:
  `uv run ruff check apps/server/dimoo_run/runtime/capacity.py apps/server/dimoo_run/api/console/workers.py apps/server/dimoo_run/domain/models.py apps/server/dimoo_run/api/native/runtime.py tests/api/test_worker_capacity_console.py migrations/versions/0001_baseline.py`
- Local Console contract, unit, and build proof:
  `npm run test`
  `npm run test:unit`
  `npm run build:e2e`
- Local targeted browser workflow proof:
  `npx playwright test tests/e2e/runtime-capacity.spec.ts --project=chrome --output test-results-0j`
- Local CI-style 0J browser workflow proof with isolated report output:
  `npm run test:e2e:0j`

These checks prove:

- worker heartbeat/drain/version/capacity/liveness read models;
- agent instance detail with worker assignment, concurrency, and runtime config hash;
- capacity summary with queue drilldown, retry/dead-letter pressure, and operator recommendation;
- blocked drain behavior for critical attempts;
- successful drain confirmation path;
- agent instance failure navigation into worker drilldown;
- persisted worker snapshots surviving separate registry instances;
- worker control writes that stay scoped to the requested environment even when
  the same `worker_id` is reused; and
- environment-safe capacity aggregation and worker detail that no longer count
  or display tasks from another environment that reused the same `worker_id`.

## Remaining External Evidence

1. Hosted CI artifact proving the default Playwright-managed Chromium cache path
   for the dedicated 0J workflow. The workflow path is:
   `npx playwright install --with-deps chromium`
   `npm run test:e2e:0j`
2. Hosted browser evidence that the worker capacity workflow stays green for
   capacity recommendation, blocked drain, successful drain, worker drilldown,
   and agent-instance-to-worker navigation.

## Latest Local Result

Date checked: 2026-06-10

Status: `local-ci-style-wrapper-pass`

Observed outcome:

- Backend worker/capacity suites passed locally.
- Console contract tests, unit tests, and e2e build passed locally.
- The targeted Playwright runtime capacity spec passed locally.
- The dedicated `npm run test:e2e:0j` wrapper also completed locally on
  2026-06-10 and produced `apps/console/test-results-0j`, proving the
  phase-specific wrapper path is executable on this Windows machine.
- Reused-`worker_id` regressions now pass locally, proving worker actions and
  capacity views stay isolated to the requested environment.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`

## Acceptance For Closing 0J

0J can be treated as locally complete when all of the following stay true:

1. The bounded 0J backend worker/capacity suites stay green.
2. The targeted runtime capacity browser spec stays green.
3. The dedicated `npm run test:e2e:0j` wrapper stays green.
4. Console continues to show worker health, agent instance detail, queue
   drilldown, blocked drain reasons, and safe drain confirmation in browser
   proof.
