import { defineConfig, devices } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromeEnvName = "DIMOORUN_PLAYWRIGHT_CHROME";
const localEnvFile = ".env.e2e.local";

function readLocalEnv(name: string): string | undefined {
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

const localChromeExecutable = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);

export default defineConfig({
  testDir: "./tests/e2e-live",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  outputDir: join(tmpdir(), "dimoorun-console-playwright-live-results"),
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:4174",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chrome",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: localChromeExecutable ? { executablePath: localChromeExecutable } : undefined,
      },
    },
  ],
});
