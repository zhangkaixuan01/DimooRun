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
