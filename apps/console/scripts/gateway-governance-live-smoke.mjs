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
  await page.waitForURL(/\/dashboard(?:\?|#|$)/, { timeout: 10_000 });
  await page.getByRole("heading", { name: "Dashboard" }).waitFor({ state: "visible", timeout: 10_000 });
}

export async function runGatewayGovernanceLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/governance/model-gateways`);
    await page.getByRole("heading", { name: "Model Gateway Workbench" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Gateway name").fill("primary-openai");
    await page.getByLabel("Credential reference").fill("secret:model-openai");
    await page.getByLabel("Monthly budget").fill("500");
    await page.getByLabel("Fallback gateway").fill("gateway:backup-openai");
    await page.getByRole("button", { name: "Test gateway" }).click();
    await page.getByText("Credential valid").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Health: ok").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Budget: $500").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Fallback: gateway:backup-openai").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("provider_unavailable").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("model_gateway.test").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Credential reference").fill("sk-plaintext");
    await page.getByRole("button", { name: "Test gateway" }).click();
    await page.getByText("credential_ref_must_use_secret_ref").waitFor({ state: "visible", timeout: 10_000 });
    logStep("model gateway validation surfaced health budget fallback and blocked plaintext credentials");

    await page.goto(`${frontendBaseUrl}/governance/tools`);
    await page.getByRole("heading", { name: "Tool Gateway Workbench" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Tool name").fill("crm.update_ticket");
    await page.getByLabel("Risk level").selectOption("write");
    await page.getByLabel("Tool arguments").fill('{"ticket_id":"T-100","status":"closed"}');
    await page.getByRole("button", { name: "Dry run tool" }).click();
    await page.getByText("Schema valid").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Risk: write").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Policy: require_approval").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Approval: required").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("link", { name: "Usage history" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("tool.dry_run").waitFor({ state: "visible", timeout: 10_000 });
    logStep("tool dry-run surfaced schema risk approval and audit context");

    await page.goto(`${frontendBaseUrl}/governance/secrets`);
    await page.getByRole("heading", { name: "Secret Rotation" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Secret name").fill("model-openai");
    await page.getByLabel("Secret reference").fill("vault://project/model-openai");
    await page.getByLabel("Used by").fill("gateway:primary-openai");
    await page.getByRole("button", { name: "Validate secret" }).click();
    await page.getByText("Secret valid").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("gateway:primary-openai").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("secret.validate").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Value hidden").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Secret reference").fill("plaintext:model-openai-next");
    await page.getByText("Secret reference must use an external provider URI.").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Secret reference").fill("vault://project/model-openai-next");
    await page.getByLabel("Rotation reason").fill("scheduled rotation");
    await page.getByRole("button", { name: "Rotate secret" }).click();
    await page.getByText("Rotated: rotated").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("vault://project/model-openai-next").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("secret.rotate").waitFor({ state: "visible", timeout: 10_000 });
    logStep("secret validation and rotation preserved audit visibility without exposing values");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runGatewayGovernanceLiveSmoke();
}
