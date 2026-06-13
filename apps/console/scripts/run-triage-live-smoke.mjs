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

async function getJson(url, options = {}) {
  const response = await fetch(url, {
    method: "GET",
    headers: {
      ...(options.headers || {}),
    },
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
  return String(loginResponse.body.access_token);
}

function scopedHeaders(token, requestId) {
  return {
    Authorization: `Bearer ${token}`,
    "X-Tenant-Id": "1",
    "X-Project-Id": "1",
    "X-Environment": "local",
    "X-Request-Id": requestId,
  };
}

function resolveLiveFixture() {
  const fixturePath = process.env.DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE
    || join(tmpdir(), "dimoorun-console-live-e2e", "live-gateway-fixture.json");
  assert.equal(existsSync(fixturePath), true, `Missing live workflow fixture file: ${fixturePath}`);
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
  const replay = fixture.replay_triage;
  assert.equal(typeof replay?.source_run_id, "number", JSON.stringify(fixture));
  assert.equal(typeof replay?.candidate_agent_version_id, "number", JSON.stringify(fixture));
  return replay;
}

export async function runRunTriageLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const token = await login(apiBaseUrl);
  const fixture = resolveLiveFixture();
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/runs/${fixture.source_run_id}/triage`);
    await page.getByRole("heading", { name: `Run triage #${fixture.source_run_id}` }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("cell", { name: "provider timeout" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("heading", { name: "Timeline" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("heading", { name: "Attempts" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("heading", { name: "Audit evidence" }).waitFor({ state: "visible", timeout: 10_000 });
    logStep("triage opened");

    await page.getByRole("link", { name: "Compare replay" }).click();
    await page.waitForURL(new RegExp(`/replay/compare\\?source_run_id=${fixture.source_run_id}`), { timeout: 10_000 });
    await page.getByRole("heading", { name: "Replay comparison" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Candidate version").selectOption(String(fixture.candidate_agent_version_id));
    await page.getByLabel("Replay config").fill('{"temperature":0,"dataset_label":"incident-triage"}');
    await page.getByRole("button", { name: "Create comparison" }).click();
    await page.getByText(/Comparison #cmp_/).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText(`Source run #${fixture.source_run_id}`).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Replay run #").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Source remains immutable", { exact: true }).waitFor({ state: "visible", timeout: 10_000 });

    const sourceRunAfterComparison = await getJson(`${apiBaseUrl}/v1/runs/${fixture.source_run_id}`, {
      headers: scopedHeaders(token, "req_live_phase0c_source_run"),
    });
    assert.equal(sourceRunAfterComparison.response.status, 200, JSON.stringify(sourceRunAfterComparison.body));
    assert.equal(sourceRunAfterComparison.body.id, fixture.source_run_id, JSON.stringify(sourceRunAfterComparison.body));
    assert.equal(sourceRunAfterComparison.body.status, "failed", JSON.stringify(sourceRunAfterComparison.body));

    await page.getByLabel("Dataset name").fill("support-regressions");
    await page.getByLabel("Dataset label").fill("provider-timeout");
    await page.getByRole("button", { name: "Save evidence" }).click();
    await page.getByText("Saved evidence to support-regressions").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText(`source_run_id: ${fixture.source_run_id}`).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("replay_run_id: ").waitFor({ state: "visible", timeout: 10_000 });
    logStep("replay comparison evidence captured");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runRunTriageLiveSmoke();
}
