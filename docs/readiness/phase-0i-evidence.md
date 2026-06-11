# Phase 0I Evidence Checklist

Phase 0I covers the Compatibility Migration and Runtime Explorer workflow.
The backend and Console implementation are in place. As of 2026-06-11, local
backend, Console unit/build, targeted browser evidence, and hosted CI artifact
proof all exist for the dedicated 0I workflow.

## What Is Already Proven

- Local backend compatibility workflow coverage:
  `uv run pytest -q tests/compat/test_langgraph_compat_api.py tests/api/test_compatibility_console_workflows.py tests/compatibility/test_golden_runtime_alignment.py`
- Local backend lint coverage for the 0I implementation:
  `uv run ruff check apps/server/dimoo_run/api/console/compatibility.py apps/server/dimoo_run/compatibility tests/api/test_compatibility_console_workflows.py tests/compatibility/test_golden_runtime_alignment.py`
- Local Console contract, unit, and build proof:
  `npm run test`
  `npm run test:unit`
  `npm run build:e2e`
- Local targeted browser workflow proof:
  `npx playwright test tests/e2e/compatibility-explorer.spec.ts --project=chrome`
- Local CI-style 0I browser workflow proof with isolated report output:
  `PLAYWRIGHT_HTML_REPORT=playwright-report-0i npm run test:e2e:0i`

These checks prove the Console compatibility explorer API contract, migration
report logic, golden compatibility divergence capture, request builder, stream
status probing, `Last-Event-ID` replay handling, refresh-backed reconnect
state persistence, unsupported capability explanations, and the dedicated
hosted CI/browser artifact path.

## Hosted CI Proof

- Successful hosted CI run `27225197478` on `main` from 2026-06-09 published
  `console-playwright-0i-report`.
- Successful hosted CI run `27275225184` on `main` from 2026-06-10 also
  published `console-playwright-0i-report`.
- Those artifacts were produced by the dedicated workflow path using the
  default Playwright-managed Chromium cache:
  `npx playwright install --with-deps chromium`
  `npm run test:e2e:0i`

## Latest Local Result

Date checked: 2026-06-10

Status: `local-targeted-browser-pass`

Observed outcome:

- Backend compatibility workflow suites passed locally.
- Console contract tests, unit tests, and e2e build passed locally.
- The targeted Playwright compatibility explorer spec passed locally with the
  configured Chrome path, including query-backed reconnect state after page
  reload and visible golden compatibility record output for migration and run
  actions.
- The CI-style `npm run test:e2e:0i` wrapper also completed locally on
  2026-06-10 and produced `apps/console/playwright-report-0i/index.html`,
  proving the dedicated 0I report path is wired correctly before the hosted
  runs above.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`

## Closure Verdict

0I is now considered closed for this phase because all of the following are
true:

1. The bounded 0I backend compatibility suites stay green.
2. The targeted compatibility explorer browser spec stays green.
3. The Console compatibility explorer continues to show native resource links,
   stream replay status, migration report details, golden compatibility
   records, reconnect state after reload, and unsupported capability
   explanations in browser proof.
4. Hosted CI runs have published browser evidence using the default
   Playwright-managed Chromium cache path.
