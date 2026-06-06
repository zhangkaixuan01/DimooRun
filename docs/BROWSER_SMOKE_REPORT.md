# Browser Smoke Report

This report records current local evidence for Console browser smoke and critical accessibility checks. It is not a pass report.

## Command

Working directory: `apps/console`.

```bash
npm run build:e2e
```

Working directory: `apps/console`.

```bash
npm run test:e2e
```

Browser install command attempted:

Working directory: `apps/console`.

```bash
npx playwright install chromium
```

## Result

Status: `blocked-by-local-playwright-browser-install`

Date checked: 2026-06-05

`npm run build:e2e` passes: `vue-tsc --noEmit` and `vite build --mode e2e` complete successfully.

`npm run test:e2e` does not reach application assertions locally because the Playwright Chromium executable is missing. Two `npx playwright install chromium` attempts timed out, including a retry after removing the stale Playwright cache lock left by the first timeout.

## Evidence

Successful E2E build evidence:

```text
vite v7.3.3 building client environment for e2e...
768 modules transformed.
✓ built in 4.26s
```

Browser launch failure:

```text
browserType.launch: Executable doesn't exist at C:\Users\Administrator\AppData\Local\ms-playwright\chromium_headless_shell-1223\chrome-headless-shell-win64\chrome-headless-shell.exe
Looks like Playwright was just installed or updated.
Please run the following command to download new browsers:
npx playwright install
```

Install blocker:

```text
npx playwright install chromium
command timed out after 604067 milliseconds
```

CI configuration correction completed:

```text
apps/console/playwright.config.ts no longer forces channel: "chrome".
.github/workflows/ci.yml installs Playwright chromium before npm run test:e2e.
```

## Next Action

Run the browser install and E2E suite in an environment with a working Playwright browser cache or network path:

Working directory: `apps/console`.

```bash
npx playwright install chromium
npm run test:e2e
```

If the suite passes, update this report and `docs/PRODUCTION_READINESS_SCORECARD.md` with the current output. If it fails after Chromium is installed, investigate the first failing test with Playwright trace output and keep this report as the browser evidence log.

