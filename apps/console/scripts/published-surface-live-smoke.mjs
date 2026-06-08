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

async function expectVisible(page, text) {
  await page.getByText(text).waitFor({ state: "visible", timeout: 10_000 });
}

async function fillLoginForm(page) {
  await page.locator('input[autocomplete="current-password"]').fill(
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345",
  );
  await page.locator('form.login-form button[type="submit"]').click();
}

async function waitForDashboard(page) {
  await page.waitForURL(/\/dashboard(?:\?|#|$)/, { timeout: 10_000 });
  await page.getByRole("heading", { name: "Dashboard" }).waitFor({ state: "visible", timeout: 10_000 });
}

function logStep(message) {
  const line = `Live smoke step: ${message}`;
  console.log(line);
  appendFileSync(liveE2eLogPath, `[${new Date().toISOString()}] ${line}\n`);
}

async function invokeLiveIngress(page, apiBaseUrl, requestId) {
  return page.evaluate(async ({ baseUrl, requestId: liveRequestId }) => {
    const response = await fetch(`${baseUrl}/v1/ingress/support/triage`, {
      method: "POST",
      headers: {
        Authorization: "Bearer runtime-token",
        "Content-Type": "application/json",
        "X-Request-Id": liveRequestId,
      },
      body: JSON.stringify({ ticket_id: "INC-LIVE-BROWSER" }),
    });
    return { status: response.status, body: await response.json() };
  }, { baseUrl: apiBaseUrl, requestId });
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

function resolveLiveFixture() {
  const fixturePath = process.env.DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE
    || join(tmpdir(), "dimoorun-console-live-e2e", "live-gateway-fixture.json");
  assert.equal(existsSync(fixturePath), true, `Missing live gateway fixture file: ${fixturePath}`);
  const fixture = JSON.parse(readFileSync(fixturePath, "utf8"));
  assert.equal(typeof fixture.deployment_id, "number", JSON.stringify(fixture));
  return fixture;
}

async function createLiveSurface(apiBaseUrl) {
  const adminEmail = process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun";
  const adminPassword = process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345";
  const login = await postJson(`${apiBaseUrl}/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });
  assert.equal(login.response.status, 200, JSON.stringify(login.body));

  const token = String(login.body.access_token);
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Tenant-Id": "1",
    "X-Project-Id": "1",
    "X-Environment": "local",
    "X-Request-Id": "req_live_setup",
  };
  const fixture = resolveLiveFixture();

  const surface = await postJson(`${apiBaseUrl}/v1/published-surfaces`, {
    headers,
    data: {
      name: "live-browser-support-surface",
      deployment_id: fixture.deployment_id,
      type: "http",
      status: "active",
    },
  });
  assert.equal(surface.response.status, 201, JSON.stringify(surface.body));

  const surfaceId = Number(surface.body.item.id);
  const route = await postJson(`${apiBaseUrl}/v1/ingress-routes`, {
    headers,
    data: {
      name: "live-browser-support-route",
      surface_id: surfaceId,
      path: "/support/triage",
      auth_mode: "api_key",
      status: "active",
    },
  });
  assert.equal(route.response.status, 201, JSON.stringify(route.body));

  return { surfaceId, deploymentId: fixture.deployment_id, token };
}

async function fetchSurfaceDetail(apiBaseUrl, token, surfaceId) {
  const detail = await getJson(`${apiBaseUrl}/v1/console/published-surfaces/${surfaceId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": "1",
      "X-Project-Id": "1",
      "X-Environment": "local",
      "X-Request-Id": "req_live_surface_detail",
    },
  });
  assert.equal(detail.response.status, 200, JSON.stringify(detail.body));
  return detail.body;
}

export async function runPublishedSurfaceLiveSmoke({
  frontendBaseUrl = "http://127.0.0.1:4174",
  apiBaseUrl = "http://127.0.0.1:4180",
} = {}) {
  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : {};
  const frontendOrigin = new URL(frontendBaseUrl).origin;
  const setup = await createLiveSurface(apiBaseUrl);
  const browser = await chromium.launch(launchOptions);

  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
    await page.goto(`${frontendBaseUrl}/login`);
    await fillLoginForm(page);
    await waitForDashboard(page);

    await page.goto(`${frontendBaseUrl}/published-surfaces/${setup.surfaceId}`);
    await page.getByRole("heading", { name: "Governed Published Surface" }).waitFor({ state: "visible", timeout: 10_000 });
    await page.getByLabel("Route path").fill("/support/triage");
    await page.getByLabel("Deployment").fill(String(setup.deploymentId));
    await page.getByLabel("Auth mode").fill("api_key");
    await page.getByLabel("Allowed origins").fill(frontendOrigin);
    await page.getByLabel("Requests per minute").fill("120");
    await page.getByRole("button", { name: "Validate publish" }).click();
    await expectVisible(page, "Publish validation: valid");
    await page.getByRole("button", { name: "Publish surface" }).click();
    await expectVisible(page, "Surface published");

    await page.getByLabel("Synthetic path").fill("/support/triage");
    await page.getByLabel("Synthetic method").fill("POST");
    await page.getByRole("button", { name: "Test route" }).click();
    await expectVisible(page, "Route test: matched");
    await expectVisible(page, "auth: allow");
    await expectVisible(page, "policy: allow");
    logStep("route test completed");
    await page.getByRole("button", { name: "Open request log" }).click();
    await expectVisible(page, "authorization: [REDACTED]");
    logStep("request log opened");

    await page.getByLabel("Candidate traffic").fill("20");
    await page.getByRole("button", { name: "Apply traffic split" }).click();
    await expectVisible(page, "traffic_split");
    await expectVisible(page, "candidate: 20");
    logStep("traffic split applied");

    const liveIngress = await invokeLiveIngress(page, apiBaseUrl, "req_live_browser_ingress");
    assert.equal(liveIngress.status, 200, JSON.stringify(liveIngress.body));
    assert.equal(liveIngress.body.status, "accepted", JSON.stringify(liveIngress.body));

    await page.goto(`${frontendBaseUrl}/published-surfaces/${setup.surfaceId}`);
    await expectVisible(page, "Exposure health: ready");
    await expectVisible(page, "status 200 / trace_");
    await expectVisible(page, "traffic canary recorded");

    await page.getByRole("button", { name: "Revoke surface" }).click();
    await page.getByLabel("Danger confirmation").fill(`REVOKE SURFACE ${setup.surfaceId}`);
    await page.getByRole("button", { name: "Confirm revoke" }).click();
    await expectVisible(page, "published_surface.revoke");
    await expectVisible(page, "Exposure health: blocked");
    await expectVisible(page, "surface_revoked");

    await page.getByRole("button", { name: "Rollback surface" }).click();
    await expectVisible(page, "Exposure health: ready");
    const rollbackDetail = await fetchSurfaceDetail(apiBaseUrl, setup.token, setup.surfaceId);
    assert.equal(
      rollbackDetail.rollout_history.at(-1)?.operation,
      "rollback",
      JSON.stringify(rollbackDetail.rollout_history),
    );
    assert.equal(
      rollbackDetail.rollout_history.at(-1)?.rollback_to_version,
      1,
      JSON.stringify(rollbackDetail.rollout_history.at(-1)),
    );

    const rollbackIngress = await invokeLiveIngress(page, apiBaseUrl, "req_live_browser_rollback");
    assert.equal(rollbackIngress.status, 200, JSON.stringify(rollbackIngress.body));
    assert.equal(rollbackIngress.body.status, "accepted", JSON.stringify(rollbackIngress.body));

    await page.goto(`${frontendBaseUrl}/published-surfaces/${setup.surfaceId}`);
    await expectVisible(page, "Exposure health: ready");
    logStep("rollback completed");
  } finally {
    await browser.close();
  }
}

if (import.meta.url === `file://${process.argv[1].replaceAll("\\", "/")}`) {
  await runPublishedSurfaceLiveSmoke();
}
