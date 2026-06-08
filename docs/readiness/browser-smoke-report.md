# Browser Smoke Report

This report records current local evidence for Console browser smoke and critical
accessibility checks. It includes mocked Console browser proof plus the latest
separate local real-terminal Phase 0H live-backend browser proof. It is still
not a hosted CI proof.

## Command

Working directory: `apps/console`.

```bash
npm run check:e2e-browser
```

Working directory: `apps/console`.

```bash
npm run test:e2e
```

Default browser install command for clean environments:

Working directory: `apps/console`.

```bash
npx playwright install chromium
```

Offline/local fallback:

Working directory: `apps/console`.

```powershell
Copy-Item .env.e2e.example .env.e2e.local
npm run check:e2e-browser
npm run test:e2e
```

## Result

Status: `local-pass-with-supplied-chrome`

Date checked: 2026-06-07

`npm run check:e2e-browser` passes with `DIMOORUN_PLAYWRIGHT_CHROME` loaded from the ignored local `apps/console/.env.e2e.local` file.

`npm run test:e2e` passes locally using the supplied Chrome executable. The suite builds the e2e bundle and runs 34 Playwright tests.

This mocked suite does not by itself prove hosted CI or the default
Playwright-managed browser cache. Real live-backend and ingress evidence is
tracked separately below.

Live-backend launcher self-check evidence:

Working directory: `apps/console`.

```bash
node scripts/start-live-backend.mjs --check
```

Local verification on 2026-06-07 showed the launcher could:

- start the temporary backend on `127.0.0.1:4180`
- return `200 OK` from `/docs`
- exit with code `0`
- release `4180` after shutdown

The launcher now also fails fast with `Port 4180 is already in use on 127.0.0.1` so stale listeners do not produce false-positive live-backend proof.

## Evidence

Browser self-check evidence:

```text
Using Chrome executable from DIMOORUN_PLAYWRIGHT_CHROME: C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe
```

Successful E2E build evidence:

```text
vite v7.3.3 building client environment for e2e...
768 modules transformed.
✓ built in 4.42s
```

Playwright result:

```text
Running 34 tests using 8 workers
34 passed (21.1s)
```

Covered workflow groups in this local mocked run:

- Console smoke and authenticated shell.
- Critical axe checks for dashboard, login, dense table, drawer flow, and high-risk confirmation.
- Deployment promotion, pause/resume, policy denial, and stale conflict.
- Package validation and readiness blockers.
- Policy approval and human-task decisions.
- Model gateway, tool gateway, and secret governance.
- Published Surface publish, invalid route blocking, exposure-health display, route test, request-log drilldown, traffic split, revoke confirmation, and rollback.
- Quality loop, replay comparison, incident/notification/recovery, and generic workflow shell states.

## Separate Live 0H Proof

Working directory: `apps/console`.

```powershell
npm run cleanup:e2e:live
npm run test:e2e:live:local
```

Result:

Status: `local-live-pass-real-terminal`

Date checked: 2026-06-09

Observed outcome:

- the live wrapper completed from a normal Windows terminal
- the governed browser path reached route test, request-log drilldown, traffic
  split, live ingress, revoke, rollback, and post-rollback ingress acceptance
- `npm run verify:e2e:live-report` accepted the generated
  `%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`
- cleanup completed after verification

This closes the local live-browser gap for 0H. It does not yet replace hosted
CI/browser proof with the default Playwright-managed Chromium path.

## Next Action

Run the same suite in hosted CI with the default Playwright-managed Chromium cache:

Working directory: `apps/console`.

```bash
npx playwright install chromium
npm run test:e2e
```

Then add hosted browser proof for the workflows that still depend on local-only
or mocked evidence, especially Published Surface / Ingress / Agent Gateway,
deployment promotion, policy approval, and recovery flows.

The CI workflow now includes an explicit Phase 0H browser command after the
managed Chromium install:

Working directory: `apps/console`.

```bash
npm run test:e2e:0h
```

That command runs `tests/e2e/published-surfaces.spec.ts` with the `chrome`
project, and CI uploads the Playwright report artifact. This is configured
evidence plumbing, not yet a hosted pass claim until a current CI run publishes
the report.

The Published Surface / Ingress / Agent Gateway live-backend proof path is now
scripted and has a current local real-terminal pass:

Working directory: `apps/console`.

```bash
npm run test:e2e:live
```

This command expects a current `npm run build:e2e` bundle, patches the local
e2e API base from the mock endpoint to `127.0.0.1:4180`, starts a temporary
real backend on `127.0.0.1:4180`, serves the Console on `127.0.0.1:4174`, and
runs a single-process published-surface live smoke script. The single-process
smoke replaces the Playwright Test Runner worker path for this live proof
because the local Windows tool environment previously hit
`WorkerHost.startRunner` `spawn EPERM` when Playwright tried to fork a worker.
The live backend launcher now writes launcher, uv, and uvicorn worker PIDs to a
PID file consumed by the runner cleanup path, so cleanup can target the backend
process tree with Node `process.kill()` before falling back to external port
scans.

Current local evidence shows it can finish cleanly, verify its generated report,
and leave cleanup to the wrapper path without preserving a stale failure marker
in the report file.

For local Windows verification, use the foreground terminal wrapper instead of
running the live command through a redirected automation session:

Working directory: `apps/console`.

```powershell
npm run cleanup:e2e:live
npm run test:e2e:live:local
```

The wrapper runs `npm run check:e2e-browser`, `npm run build:e2e`,
`node scripts/run-live-e2e.mjs`, and `npm run verify:e2e:live-report`, then
always runs `npm run cleanup:e2e:live` in a PowerShell `finally` block. It sets
`DIMOORUN_LIVE_E2E_TIMEOUT_MS=120000` unless the caller provides a different
timeout.

`npm run verify:e2e:live-report` accepts the default
`%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log` only when it contains live
backend readiness, live frontend readiness, the published-surface live smoke
completion marker, explicit route-test/request-log/traffic-split/rollback step
markers, and service cleanup in the expected order, and rejects reports that
contain hard timeout, `spawn EPERM`, or early service-exit markers.

If a local live smoke run is interrupted, clean up the temporary backend and frontend listeners before retrying:

Working directory: `apps/console`.

```bash
npm run cleanup:e2e:live
```

The single source of truth for the remaining 0H closeout evidence is:

- [Phase 0H Evidence Checklist](phase-0h-evidence.md)
