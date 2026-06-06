import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const envName = "DIMOORUN_PLAYWRIGHT_CHROME";
const localEnvFile = ".env.e2e.local";

function readLocalEnv(name) {
  const envPath = join(process.cwd(), localEnvFile);
  if (!existsSync(envPath)) return undefined;

  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;

    const key = trimmed.slice(0, separator).trim();
    if (key !== name) continue;

    return trimmed.slice(separator + 1).trim().replace(/^["']|["']$/g, "");
  }

  return undefined;
}

const configuredChrome = process.env[envName] || readLocalEnv(envName);

function printFallback() {
  console.error("Playwright Chromium is not available for Console E2E tests.");
  console.error("Install the managed browser cache:");
  console.error("  npx playwright install chromium");
  console.error("");
  console.error("For offline or restricted networks, point to a local Chrome/Chromium executable:");
  console.error(`  $env:${envName} = "C:\\\\path\\\\to\\\\chrome-win64\\\\chrome.exe"`);
  console.error("");
  console.error(`Or copy .env.e2e.example to ${localEnvFile} and set:`);
  console.error(`  ${envName}=C:\\\\path\\\\to\\\\chrome-win64\\\\chrome.exe`);
}

if (configuredChrome) {
  if (!existsSync(configuredChrome)) {
    console.error(`${envName} is set, but the file does not exist: ${configuredChrome}`);
    printFallback();
    process.exit(1);
  }

  console.log(`Using Chrome executable from ${envName}: ${configuredChrome}`);
  process.exit(0);
}

const managedChromium = chromium.executablePath();

if (existsSync(managedChromium)) {
  console.log(`Using Playwright-managed Chromium: ${managedChromium}`);
  process.exit(0);
}

printFallback();
process.exit(1);
