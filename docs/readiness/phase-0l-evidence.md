# Phase 0L Evidence Checklist

Phase 0L covers the Platform Settings, Providers, and Dangerous Configuration
workflow. As of 2026-06-11, the backend workflow and Console implementation are
in place and locally verified through backend tests, Console contract tests,
unit tests, e2e bundle build proof, and a shared browser runner that executes
the 0L cases before a dedicated 0L verifier emits the phase report.

## What Is Already Proven

- Local backend workflow coverage:
  `uv run pytest -q tests/api/test_platform_settings_workflows.py tests/production_foundation/test_ci_workflow.py`
- Local backend type-check coverage:
  `uv run mypy apps/server tests scripts`
- Local Console contract, unit, and build proof:
  `npm run test`
  `npm run test:unit`
  `npm run build:e2e`
- Shared local browser runner and dedicated 0L verifier:
  `npm run test:e2e:0j`
  `npm run test:e2e:0l`
- Dedicated CI artifact wiring exists:
  `PLAYWRIGHT_HTML_REPORT=playwright-report-0l`
  `console-playwright-0l-report`

These checks prove:

- `/v1/console/settings/platform` returns runtime mode, database mode, queue
  backend, object store, secret provider, model gateway provider, artifact
  retention, trace retention, CORS, production safety, scope defaults, and
  dangerous-state snapshot data;
- `/v1/console/settings/providers` reports Postgres, Redis, object store,
  secret provider, model gateway, webhook transport, notification transport,
  and observability exporter status;
- scoped defaults can be read and updated, while production mode blocks
  organization and project writes but still permits environment-scoped changes;
- dangerous configuration preflight and apply flows now return typed
  confirmation phrases, affected-resource previews, rollback notes, and
  audit-backed results; the Console now renders those previews and result
  envelopes directly in the Danger Zone workflow; and
- the Console now separates user preferences from platform settings, provider
  status, and the danger zone while showing organization/project/environment
  configuration boundaries on the Platform Settings page.

## Remaining External Evidence

1. Hosted CI artifact proving the default Playwright-managed Chromium cache path
   for the shared `0J` runner and the derived dedicated `0L` phase report.
2. Hosted browser evidence that the platform settings pages stay green for
   readonly production messaging, provider outage display, environment default
   update, blocked dangerous preflight, and successful audited apply.

As of 2026-06-11, the latest successful hosted CI run visible from GitHub is
run `27275225184` on `main` from 2026-06-10. That run published
`console-playwright-report`, `console-playwright-0h-report`,
`console-playwright-0i-report`, and `console-playwright-0j-report`, but it did
not publish `console-playwright-0l-report`, so it cannot serve as 0L hosted
closure evidence for the current implementation.

## Latest Local Result

Date checked: 2026-06-11

Status: `local-shared-browser-proof-pass`

Observed outcome:

- Backend 0L workflow tests passed locally.
- Global backend mypy passed locally after the 0L implementation landed.
- Console contract tests, unit tests, and E2E build passed locally.
- The shared runtime-capacity browser runner (`npm run test:e2e:0j`) now passes
  locally with the four 0L platform-settings cases co-located in the same
  browser session suite.
- The dedicated `npm run test:e2e:0l` path now verifies the shared runner proof
  marker and emits a dedicated `playwright-report-0l` artifact without
  re-running the flaky Windows Playwright worker fork path.
- The shared runner now clears stale `.phase-e2e-proof.json` state before each
  browser attempt so a failed `0J` rerun cannot leave a false-positive `0L`
  verifier result behind.

## Local Operator Notes

- Working directory for Console/browser commands: `apps/console`
- Offline/local browser fallback:
  set `DIMOORUN_PLAYWRIGHT_CHROME` in `apps/console/.env.e2e.local`
- Example value:
  `DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe`
- Generated proof marker and transient runner folders are local artifacts:
  `apps/console/.phase-e2e-proof.json` and `apps/console/tr-*`

## Acceptance For Closing 0L

0L can move beyond `partial` only when all of the following are true:

1. The bounded 0L backend workflow suites stay green.
2. The shared browser runner stays green through `npm run test:e2e:0j`.
3. The dedicated `npm run test:e2e:0l` verifier keeps accepting the shared
   phase proof and emitting the phase-specific report.
4. Hosted CI publishes the dedicated 0L Playwright artifact using the default
   Playwright-managed Chromium cache path.
5. The browser workflow proves readonly production settings, provider outage
   visibility, environment-default update, dangerous-preflight blocking, and
   successful audited dangerous apply.
