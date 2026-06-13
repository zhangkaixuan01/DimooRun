import assert from "node:assert/strict";
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

async function postJson(url, options) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: JSON.stringify(options.data || {}),
  });
  const body = await response.json();
  return { response, body };
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

async function login(apiBaseUrl) {
  const adminEmail = process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun";
  const adminPassword = process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345";
  const loginResponse = await postJson(`${apiBaseUrl}/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });
  assert.equal(loginResponse.response.status, 200, JSON.stringify(loginResponse.body));
}

function resolveFixture() {
  const fixturePath = process.env.DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE
    || join(tmpdir(), "dimoorun-console-live-e2e", "live-gateway-fixture.json");
  assert.equal(existsSync(fixturePath), true, `Missing live workflow fixture file: ${fixturePath}`);
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
  const replay = fixture.replay_triage;
  const promotion = fixture.deployment_promotion;
  assert.equal(typeof replay?.source_run_id, "number", JSON.stringify(fixture));
  assert.equal(typeof promotion?.deployment_id, "number", JSON.stringify(fixture));
  assert.equal(typeof promotion?.candidate_agent_version_id, "number", JSON.stringify(fixture));
  return {
    sourceRunId: replay.source_run_id,
    agentId: promotion.agent_id,
    candidateVersionId: promotion.candidate_agent_version_id,
    deploymentId: promotion.deployment_id,
  };
}

function parseExperimentRunId(text) {
  const match = text.match(/#(\d+)/);
  assert.ok(match, `Could not parse experiment run id from: ${text}`);
  return Number(match[1]);
}

export async function runQualityLoopLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const fixture = resolveFixture();
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/observability/datasets`);
    await page.getByRole("heading", { name: "Dataset Capture" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Dataset name").fill("live-quality-regressions");
    await page.getByLabel("Source run").fill(String(fixture.sourceRunId));
    await page.getByLabel("Dataset label").fill("provider-timeout");
    await page.getByLabel("Redact fields").fill("ticket_id");
    await page.getByRole("button", { name: "Capture run" }).click();
    await page.getByText(/Captured dataset item #|Duplicate item reused/).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText(`source_run_id: ${fixture.sourceRunId}`).waitFor({ state: "visible", timeout: 10_000 });
    logStep("dataset capture preserved provenance and redaction preview");

    await page.goto(`${frontendBaseUrl}/observability/experiments`);
    await page.getByRole("heading", { name: "Experiment Workbench" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Experiment name").fill("live-quality-gate");
    await page.getByLabel("Dataset").fill("21");
    await page.getByLabel("Candidate version").fill(String(fixture.candidateVersionId));
    await page.getByLabel("Agent").fill(String(fixture.agentId));
    await page.getByLabel("Minimum score").fill("0.8");
    await page.getByRole("button", { name: "Run experiment" }).click();
    const experimentHeading = page.getByText(/Experiment run #\d+/);
    await experimentHeading.waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Quality gate: passed").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Promotion: allowed").waitFor({ state: "visible", timeout: 10_000 });
    const experimentRunId = parseExperimentRunId(await experimentHeading.textContent() || "");
    logStep("experiment run produced a passing quality gate for the candidate");

    await page.goto(`${frontendBaseUrl}/observability/quality-gate`);
    await page.getByRole("heading", { name: "Quality Gate" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Deployment").fill(String(fixture.deploymentId));
    await page.getByLabel("Candidate version").fill(String(fixture.candidateVersionId));
    await page.getByLabel("Experiment run").fill(String(experimentRunId));
    await page.getByRole("button", { name: "Preview gate" }).click();
    await page.getByText("Quality gate: passed").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Promotion: allowed").waitFor({ state: "visible", timeout: 10_000 });
    logStep("quality gate preview linked experiment evidence to promotion eligibility");

    await page.goto(`${frontendBaseUrl}/deployments/${fixture.deploymentId}`);
    await page.getByRole("heading", { name: "Deployments", exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("tab", { name: "Promotion" }).click();
    await page.getByLabel("Candidate version").selectOption(String(fixture.candidateVersionId));
    await page.getByLabel("Experiment run").fill(String(experimentRunId));
    await page.getByRole("button", { name: "Preview promotion" }).click();
    await page.getByRole("heading", { name: "Impact preview" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Quality Gate: passed").waitFor({ state: "visible", timeout: 10_000 });
    logStep("deployment promotion preview required visible quality evidence");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runQualityLoopLiveSmoke();
}
