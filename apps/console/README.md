# DimooRun Console

## Browser Tests

The Console E2E suite uses Playwright Chromium by default. After cloning the
project and installing npm dependencies, prepare the browser cache from
`apps/console`:

```powershell
npx playwright install chromium
npm run check:e2e-browser
```

Then run:

```powershell
npm run test:e2e
```

For the focused Phase 6 browser workflow proof, run:

```powershell
npx playwright test tests/e2e/console-runtime.spec.ts tests/e2e/accessibility.spec.ts tests/e2e/responsive-snapshots.spec.ts --project=chrome --output test-results-phase6-final
```

If the Playwright download is blocked by an offline or restricted network, use a
local Chrome/Chromium executable instead. Copy the checked-in example file and
fill in your machine-specific path:

```powershell
Copy-Item .env.e2e.example .env.e2e.local
notepad .env.e2e.local
npm run check:e2e-browser
npm run test:e2e
```

Example `.env.e2e.local` value:

```text
DIMOORUN_PLAYWRIGHT_CHROME=C:\Users\Administrator\AppData\Local\Temp\dimoorun-playwright-chrome\chrome-win64\chrome.exe
```

The executable can live anywhere on the machine. The important part is that
`DIMOORUN_PLAYWRIGHT_CHROME` points directly to `chrome-win64\chrome.exe`.

## Phase 6 Browser Proof

Phase `6` is the first dedicated browser workflow expansion layer on top of the
shared smoke suite. From `apps/console`, run:

```powershell
npx playwright test tests/e2e/console-runtime.spec.ts tests/e2e/accessibility.spec.ts tests/e2e/responsive-snapshots.spec.ts --project=chrome --output test-results-phase6-final
```

This focused Phase 6 browser command executes the dedicated runtime workflow
spec, accessibility spec, and responsive screenshot spec together. The command proves
login, agent registration, AgentVersion creation, Deployment creation,
Deployment task submission, Run detail inspection, replay comparison, empty /
loading / error / offline states, key-page axe coverage, and mobile/desktop
workflow screenshots in one focused report artifact. It reuses the current e2e
build output, so run `npm run build:e2e` first if you have not already built
the Console in e2e mode.

## Phase 0L Browser Proof

Phase `0L` currently reuses the shared runtime-capacity browser runner instead
of launching a separate Playwright worker path on this Windows machine. From
`apps/console`, run:

```powershell
npm run test:e2e:0j
npm run test:e2e:0l
```

`test:e2e:0j` executes the shared browser suite, including the four 0L settings
workflow assertions, and writes `.phase-e2e-proof.json`. `test:e2e:0l` verifies
that proof marker and emits the dedicated `playwright-report-0l` artifact
without re-running the flaky standalone worker fork path.

## Live 0H Smoke

The live Published Surface / Ingress smoke uses the real local backend and is
intended to be run from a normal Windows terminal, not through a redirected tool
session. From `apps/console`:

```powershell
npm run cleanup:e2e:live
npm run test:e2e:live:local
```

`test:e2e:live:local` checks the browser config, builds the e2e bundle, runs the
single-process live smoke, verifies the generated live report, and then runs
cleanup in a `finally` block. The wrapper sets
`DIMOORUN_LIVE_E2E_TIMEOUT_MS=120000` by default if you have not provided your
own timeout.

To verify a copied log separately:

`verify:e2e:live-report` reads the default live log at
`%TEMP%\dimoorun-console-live-e2e\run-live-e2e.log`. To verify a copied log:

```powershell
npm run verify:e2e:live-report -- --log C:\path\to\run-live-e2e.log
```

The verifier now requires explicit step markers for route test completion,
request-log drilldown, traffic-split application, rollback completion, backend
readiness, frontend readiness, smoke completion, and cleanup, and it rejects
logs where those markers appear out of order.

If the run is interrupted, clean up before retrying:

```powershell
npm run cleanup:e2e:live
```

The current 0H acceptance boundary and the remaining external evidence required
to move the phase beyond `partial` are tracked in
`docs/readiness/phase-0h-evidence.md`.

Current local status as of 2026-06-09:

- `npm run test:e2e:live:local` completed successfully from a normal Windows terminal
- `npm run verify:e2e:live-report` accepted the generated live report
- Phase `0H` still remains `partial` overall until hosted CI proves the default Playwright-managed Chromium path
