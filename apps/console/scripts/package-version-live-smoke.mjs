import assert from "node:assert/strict";
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { chromium } from "@playwright/test";

const chromeEnvName = "DIMOORUN_PLAYWRIGHT_CHROME";
const localEnvFile = ".env.e2e.local";
const liveE2eLogPath = join(tmpdir(), "dimoorun-console-live-e2e", "run-live-e2e.log");
const liveAgentName = "live-browser-support-agent";

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

async function expectVisible(page, text) {
  await page.getByText(text).waitFor({ state: "visible", timeout: 10_000 });
}

async function fillLoginForm(page) {
  await page.locator('input[autocomplete="username"]').waitFor({ state: "visible", timeout: 10_000 });
  await page.locator('input[autocomplete="username"]').fill(
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun",
  );
  await page.locator('input[autocomplete="current-password"]').fill(
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345",
  );
  await page.locator("form.login-form button[type='submit']").click();
}

async function waitForDashboard(page) {
  await page.waitForFunction(() => window.location.pathname === "/dashboard", undefined, { timeout: 10_000 });
  await page.getByRole("heading", { name: "Dashboard" }).waitFor({ state: "visible", timeout: 10_000 });
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

async function findAgentByName(apiBaseUrl, token, agentName) {
  const agents = await getJson(`${apiBaseUrl}/v1/agents`, {
    headers: scopedHeaders(token, "req_live_phase0a_agents"),
  });
  assert.equal(agents.response.status, 200, JSON.stringify(agents.body));
  const agent = agents.body.find((item) => item.name === agentName);
  assert.ok(agent, `Agent ${agentName} not found in ${JSON.stringify(agents.body)}`);
  return agent;
}

export async function runPackageVersionLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const token = await login(apiBaseUrl);
  const agent = await findAgentByName(apiBaseUrl, token, liveAgentName);
  const versionValue = `1.0.${Date.now()}`;
  const packageUri = `oci://registry.local/${liveAgentName}:${versionValue}`;
  const environment = `phase-0a-${Date.now()}`;
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/packages/register`);
    await page.getByRole("heading", { name: "Package Registration" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Package URI").fill(packageUri);
    await page.getByLabel("Entrypoint").fill("agent:create_agent");
    await page.getByLabel("Manifest").fill(JSON.stringify({
      name: liveAgentName,
      runtime: {
        framework: "langgraph",
        adapter: "langgraph",
        entrypoint: "agent:create_agent",
      },
      capabilities: { invoke: true, stream: true },
    }, null, 2));
    await page.getByRole("button", { name: "Validate package" }).click();
    await expectVisible(page, "create_ready_agent_version");
    await page.getByRole("button", { name: "Create ready version" }).click();
    logStep("validated package handoff completed");

    await page.getByRole("heading", { name: "Agents" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.locator(".agents-table").getByText(liveAgentName, { exact: true }).click();
    if (await page.getByText("Ready version source").count() === 0) {
      await page.locator(".agent-detail-panel").getByRole("button", { name: "Add version" }).first().click();
    }
    await page.locator("form.nested-form input[placeholder='0.1.0']").fill(versionValue);
    await page.getByRole("button", { name: "Create ready AgentVersion" }).click();
    const versionRow = page.locator("tr").filter({ hasText: versionValue }).first();
    await versionRow.waitFor({ state: "visible", timeout: 10_000 });
    await versionRow.getByText("ready").waitFor({ state: "visible", timeout: 10_000 });
    logStep("ready version created through live browser workflow");

    const versions = await getJson(`${apiBaseUrl}/v1/agents/${agent.id}/versions`, {
      headers: scopedHeaders(token, "req_live_phase0a_versions"),
    });
    assert.equal(versions.response.status, 200, JSON.stringify(versions.body));
    const createdVersion = versions.body.find((item) => item.version === versionValue);
    assert.ok(createdVersion, `Version ${versionValue} not found in ${JSON.stringify(versions.body)}`);

    const deployment = await postJson(`${apiBaseUrl}/v1/deployments`, {
      headers: scopedHeaders(token, "req_live_phase0a_deploy"),
      data: {
        agent_id: agent.id,
        agent_version_id: createdVersion.id,
        environment,
        desired_status: "active",
        replicas: 1,
        config: {},
      },
    });
    assert.equal(deployment.response.status, 201, JSON.stringify(deployment.body));

    const task = await postJson(`${apiBaseUrl}/v1/deployments/${deployment.body.id}/tasks`, {
      headers: scopedHeaders(token, "req_live_phase0a_task"),
      data: {
        input: { message: "hello from live phase 0a smoke" },
      },
    });
    assert.equal(task.response.status, 202, JSON.stringify(task.body));

    const run = await getJson(`${apiBaseUrl}/v1/runs/${task.body.run_id}`, {
      headers: scopedHeaders(token, "req_live_phase0a_run"),
    });
    assert.equal(run.response.status, 200, JSON.stringify(run.body));
    assert.equal(run.body.agent_id, agent.id, JSON.stringify(run.body));
    assert.equal(run.body.agent_version_id, createdVersion.id, JSON.stringify(run.body));
    assert.equal(run.body.deployment_id, deployment.body.id, JSON.stringify(run.body));
    logStep("deployment task accepted from validated ready version");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runPackageVersionLiveSmoke();
}
