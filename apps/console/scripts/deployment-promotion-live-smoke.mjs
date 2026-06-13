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
  const promotion = fixture.deployment_promotion;
  assert.equal(typeof promotion?.deployment_id, "number", JSON.stringify(fixture));
  assert.equal(typeof promotion?.current_agent_version_id, "number", JSON.stringify(fixture));
  assert.equal(typeof promotion?.candidate_agent_version_id, "number", JSON.stringify(fixture));
  return promotion;
}

async function createQueuedTask(apiBaseUrl, token, deploymentId) {
  const created = await postJson(`${apiBaseUrl}/v1/deployments/${deploymentId}/tasks`, {
    headers: scopedHeaders(token, "req_live_phase0b_task"),
    data: {
      input: { message: `phase-0b-preview-${Date.now()}` },
    },
  });
  assert.equal(created.response.status, 202, JSON.stringify(created.body));
  return created.body;
}

async function fetchPromotionPreview(apiBaseUrl, token, deploymentId, candidateVersionId) {
  const preview = await getJson(
    `${apiBaseUrl}/v1/deployments/${deploymentId}/promotion-preview?candidate_version_id=${candidateVersionId}`,
    { headers: scopedHeaders(token, "req_live_phase0b_preview") },
  );
  assert.equal(preview.response.status, 200, JSON.stringify(preview.body));
  return preview.body;
}

async function fetchDeployment(apiBaseUrl, token, deploymentId) {
  const deployments = await getJson(`${apiBaseUrl}/v1/deployments`, {
    headers: scopedHeaders(token, "req_live_phase0b_deployments"),
  });
  assert.equal(deployments.response.status, 200, JSON.stringify(deployments.body));
  const deployment = deployments.body.find((item) => item.id === deploymentId);
  assert.ok(deployment, `Deployment ${deploymentId} not found in ${JSON.stringify(deployments.body)}`);
  return deployment;
}

async function expectDesiredStatus(apiBaseUrl, token, deploymentId, expectedStatus) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const deployment = await fetchDeployment(apiBaseUrl, token, deploymentId);
    if (deployment.desired_status === expectedStatus) return deployment;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  const latest = await fetchDeployment(apiBaseUrl, token, deploymentId);
  assert.equal(latest.desired_status, expectedStatus, JSON.stringify(latest));
  return latest;
}

export async function runDeploymentPromotionLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const token = await login(apiBaseUrl);
  const fixture = resolveLiveFixture();
  await createQueuedTask(apiBaseUrl, token, fixture.deployment_id);
  const preview = await fetchPromotionPreview(
    apiBaseUrl,
    token,
    fixture.deployment_id,
    fixture.candidate_agent_version_id,
  );
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/deployments/${fixture.deployment_id}`);
    await page.getByRole("heading", { name: "Deployments", exact: true }).waitFor({ state: "visible", timeout: 10_000 });

    await page.getByRole("button", { name: "Pause", exact: true }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expectDesiredStatus(apiBaseUrl, token, fixture.deployment_id, "paused");
    await page.getByText("paused").first().waitFor({ state: "visible", timeout: 10_000 });
    logStep("pause action applied through live deployment workflow");

    await page.getByRole("button", { name: "Resume", exact: true }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expectDesiredStatus(apiBaseUrl, token, fixture.deployment_id, "active");
    await page.getByText("active").first().waitFor({ state: "visible", timeout: 10_000 });
    logStep("resume action applied through live deployment workflow");

    await page.getByRole("tab", { name: "Promotion" }).click();
    await page.getByLabel("Candidate version").selectOption(String(fixture.candidate_agent_version_id));
    await page.getByRole("button", { name: "Preview promotion" }).click();
    await page.getByRole("heading", { name: "Impact preview" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.locator(".impact-preview").getByText(
      `${preview.current_agent_version_id} -> ${preview.candidate_agent_version_id}`,
      { exact: true },
    ).waitFor({ state: "visible", timeout: 10_000 });
    await page.locator(".impact-preview").getByText("Active runs").waitFor({ state: "visible", timeout: 10_000 });
    await page.locator(".impact-preview").getByText("Queued tasks").waitFor({ state: "visible", timeout: 10_000 });
    await page.locator(".impact-preview").getByText("Rollback target").waitFor({ state: "visible", timeout: 10_000 });
    for (const warning of preview.warnings) {
      await page.locator(".impact-preview").getByText(warning, { exact: true }).waitFor({ state: "visible", timeout: 10_000 });
    }
    logStep("promotion impact preview surfaced runtime pressure and rollback context");

    await page.getByLabel("Rollout reason").fill("live phase 0b promote candidate");
    await page.getByRole("button", { name: "Promote candidate" }).click();
    await page.getByText("Promoted to version").waitFor({ state: "visible", timeout: 10_000 });
    const promoted = await fetchDeployment(apiBaseUrl, token, fixture.deployment_id);
    assert.equal(promoted.agent_version_id, fixture.candidate_agent_version_id, JSON.stringify(promoted));
    assert.equal(
      promoted.config?.promotion?.previous_agent_version_id,
      fixture.current_agent_version_id,
      JSON.stringify(promoted.config),
    );
    logStep("promotion applied and audit context persisted on the live deployment");

    await page.getByLabel("Rollback reason").fill("live phase 0b rollback candidate");
    await page.getByRole("button", { name: "Rollback" }).click();
    await page.getByText("Rolled back to version").waitFor({ state: "visible", timeout: 10_000 });
    const rolledBack = await fetchDeployment(apiBaseUrl, token, fixture.deployment_id);
    assert.equal(rolledBack.agent_version_id, fixture.current_agent_version_id, JSON.stringify(rolledBack));
    assert.equal(
      rolledBack.config?.promotion?.rollback_reason,
      "live phase 0b rollback candidate",
      JSON.stringify(rolledBack.config),
    );
    logStep("rollback restored the previous deployment version through the live browser workflow");

    await page.getByRole("tab", { name: "Operations" }).click();
    await page.getByRole("button", { name: "Drain", exact: true }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expectDesiredStatus(apiBaseUrl, token, fixture.deployment_id, "draining");
    await page.getByText("draining").first().waitFor({ state: "visible", timeout: 10_000 });
    logStep("drain action applied through the live deployment workflow");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runDeploymentPromotionLiveSmoke();
}
