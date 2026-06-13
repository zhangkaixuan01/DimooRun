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

async function createHumanTask(apiBaseUrl, token, suffix, payload) {
  const created = await postJson(`${apiBaseUrl}/v1/human-tasks`, {
    headers: scopedHeaders(token, `req_live_phase0d_task_${suffix}`),
    data: payload,
  });
  assert.equal(created.response.status, 201, JSON.stringify(created.body));
  return created.body.item;
}

async function getHumanTask(apiBaseUrl, token, taskId) {
  const listed = await getJson(`${apiBaseUrl}/v1/human-tasks`, {
    headers: scopedHeaders(token, `req_live_phase0d_task_lookup_${taskId}`),
  });
  assert.equal(listed.response.status, 200, JSON.stringify(listed.body));
  const task = listed.body.items.find((item) => item.id === taskId);
  assert.ok(task, `Human task ${taskId} not found in ${JSON.stringify(listed.body)}`);
  return task;
}

export async function runPolicyApprovalLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const token = await login(apiBaseUrl);
  const unique = Date.now();
  const taskApprove = await createHumanTask(apiBaseUrl, token, "approve", {
    name: `run-approval-${unique}-approve`,
    source: "deployment.promote",
    risk: "critical",
    status: "pending",
    assignee: "platform-approver",
    requester: "deploy-bot",
    risk_reason: "Policy denied direct production promotion.",
    decision_context: { run_id: 8801, deployment_id: 13 },
    diff: { desired_status: { from: "paused", to: "active" } },
  });
  const taskReject = await createHumanTask(apiBaseUrl, token, "reject", {
    name: `run-approval-${unique}-reject`,
    source: "deployment.delete",
    risk: "high",
    status: "pending",
    assignee: "platform-approver",
    requester: "security-bot",
    risk_reason: "Delete requires a second reviewer.",
    decision_context: { run_id: 8802, deployment_id: 13 },
    diff: { desired_status: { from: "active", to: "deleted" } },
  });
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/governance/policies`);
    await page.getByRole("heading", { name: "Policy workbench" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Policy name").fill(`deny-prod-delete-${unique}`);
    await page.getByLabel("Resource type").fill("deployment");
    await page.getByLabel("Action").fill("delete");
    await page.getByLabel("Decision").selectOption("deny");
    await page.getByLabel("Sample resource id").fill("42");
    await page.getByLabel("Sample environment").fill("prod");
    await page.getByLabel("Audit reason").fill("Block accidental production deletion.");
    await page.getByRole("button", { name: "Simulate policy" }).click();
    await page.getByText("Decision: deny").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "Activate policy" }).click();
    await page.getByText("Activated version 1").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("Audit comparison").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByText("decision: - -> deny").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByRole("button", { name: "Rollback policy" }).click();
    await page.getByText("Rolled back to version 1").waitFor({ state: "visible", timeout: 10_000 });
    logStep("policy workbench simulated activation and rollback");

    await page.goto(`${frontendBaseUrl}/governance/human-tasks`);
    await page.getByRole("heading", { name: "Human Tasks" }).waitFor({ state: "visible", timeout: 10_000 });
    const approveRow = page.getByRole("row", { name: new RegExp(String(taskApprove.id)) });
    const rejectRow = page.getByRole("row", { name: new RegExp(String(taskReject.id)) });
    await approveRow.getByText("deploy-bot").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel(`Decision comment for task ${taskApprove.id}`).fill("Replay comparison is clean.");
    await page.getByRole("button", { name: `Approve task ${taskApprove.id}` }).click();
    await approveRow.getByText("Resume: ready").waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel(`Decision comment for task ${taskReject.id}`).fill("Candidate version has a replay regression.");
    await page.getByRole("button", { name: `Reject task ${taskReject.id}` }).click();
    await rejectRow.getByText("Resume: blocked").waitFor({ state: "visible", timeout: 10_000 });
    logStep("human approval decisions captured with resume outcomes");

    const approved = await getHumanTask(apiBaseUrl, token, taskApprove.id);
    const rejected = await getHumanTask(apiBaseUrl, token, taskReject.id);
    assert.equal(approved.status, "approved", JSON.stringify(approved));
    assert.equal(approved.resume_outcome?.status, "ready", JSON.stringify(approved));
    assert.equal(rejected.status, "rejected", JSON.stringify(rejected));
    assert.equal(rejected.resume_outcome?.status, "blocked", JSON.stringify(rejected));
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runPolicyApprovalLiveSmoke();
}
