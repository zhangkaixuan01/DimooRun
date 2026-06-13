import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { chromium } from "@playwright/test";

const chromeEnvName = "DIMOORUN_PLAYWRIGHT_CHROME";
const localEnvFile = ".env.e2e.local";
const liveE2eLogPath = join(tmpdir(), "dimoorun-console-live-e2e", "run-live-e2e.log");

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

function logStep(message) {
  const line = `Live smoke step: ${message}`;
  console.log(line);
  appendFileSync(liveE2eLogPath, `[${new Date().toISOString()}] ${line}\n`);
}

async function fillLoginForm(page) {
  await page.locator('input[autocomplete="current-password"]').fill(
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345",
  );
  await page.locator("form.login-form button[type='submit']").click();
}

async function waitForDashboard(page) {
  await page.waitForFunction(() => window.location.pathname === "/dashboard", undefined, { timeout: 10_000 });
  await page.getByRole("heading", { name: "Dashboard" }).waitFor({ state: "visible", timeout: 10_000 });
}

export async function runEnterpriseOpsLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const browser = await chromium.launch(launchOptions);
  const incidentId = 301;

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/ops/incidents`);
    await page.getByRole("heading", { name: "Incident Triage" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Incident").fill(String(incidentId));
    await page.getByLabel("Linked run").fill("1001");
    await page.getByLabel("Linked task").fill("8001");
    await page.getByLabel("Linked event").fill("evt-1001-attempt");
    await page.getByLabel("Notification channel").fill("pagerduty-primary");
    await page.getByLabel("Audit note").fill("Escalated provider outage.");
    await page.getByRole("button", { name: "Acknowledge incident" }).click();
    await page.getByText(`Incident #${incidentId} acknowledged`).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("run: 1001").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("task: 8001").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("event: evt-1001-attempt").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("delivery: sent").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("incident.acknowledge").waitFor({ state: "visible", timeout: 10_000 });
    logStep("incident acknowledge captured audit evidence and delivery attempts");

    await page.getByLabel("Resolution summary").fill("Rerouted traffic to healthy gateway.");
    await page.getByRole("button", { name: "Resolve incident" }).click();
    await page.getByText(`Incident #${incidentId} resolved`).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("incident.resolve").waitFor({ state: "visible", timeout: 10_000 });
    logStep("incident resolve preserved resolution summary and audit timeline");

    await page.getByRole("spinbutton", { name: "Channel", exact: true }).fill("55");
    await page.getByLabel("Channel name").fill("pagerduty-primary");
    await page.getByLabel("Target ref").fill("pd://service/runtime");
    await page.getByLabel("Probe message").fill("Synthetic notification probe");
    await page.getByRole("button", { name: "Send test notification" }).click();
    await page.getByText("Notification probe sent").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("visible_to_operator: true").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("notification.test_send").waitFor({ state: "visible", timeout: 10_000 });
    logStep("notification probe exposed a visible delivery attempt");

    await page.goto(`${frontendBaseUrl}/ops/recovery`);
    await page.getByRole("heading", { name: "Backup And Restore" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Backup plan").fill("9");
    await page.getByLabel("Backup targets").fill("runs,datasets,audit_logs");
    await page.getByLabel("Storage ref").fill("s3://dimoorun-backups/local");
    await page.getByRole("button", { name: "Preview backup" }).click();
    await page.getByText("Backup dry-run ready").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("tenant_id: 1").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("backup.dry_run").waitFor({ state: "visible", timeout: 10_000 });
    logStep("backup dry-run surfaced scope proof and validation state");

    await page.getByLabel("Backup ref").fill("backup://2026-06-05/project");
    await page.getByLabel("Restore targets").fill("runs");
    await page.getByLabel("Destructive restore").check();
    await page.getByLabel("Confirmation").fill("restore");
    await page.getByRole("button", { name: "Preview restore" }).click();
    await page.getByText("destructive_restore_confirmation_required").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("RESTORE PROJECT 1").waitFor({ state: "visible", timeout: 10_000 });
    logStep("restore dry-run blocked destructive recovery without exact confirmation");

    await page.getByLabel("Confirmation").fill("RESTORE PROJECT 1");
    await page.getByRole("button", { name: "Preview restore" }).click();
    await page.getByText("Restore dry-run ready").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("restore.dry_run").waitFor({ state: "visible", timeout: 10_000 });
    logStep("restore dry-run accepted scope-matched recovery after confirmation");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runEnterpriseOpsLiveSmoke();
}
