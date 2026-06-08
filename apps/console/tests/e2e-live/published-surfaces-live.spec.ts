import { expect, test, type APIRequestContext } from "@playwright/test";

const apiBaseUrl = process.env.DIMOORUN_LIVE_API_BASE_URL || "http://127.0.0.1:4180";
const adminEmail = process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun";
const adminPassword = process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345";

type LiveSetup = {
  token: string;
  surfaceId: number;
  routeId: number;
};

test("publishes, probes, and revokes a surface against the live backend", async ({
  page,
  request,
}) => {
  const setup = await createLiveSurface(request);

  await page.goto("/login");
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Runtime Command Center" })).toBeVisible();
  const frontendOrigin = new URL(page.url()).origin;

  await page.goto(`/published-surfaces/${setup.surfaceId}`);
  await expect(page.getByRole("heading", { name: "Governed Published Surface" })).toBeVisible();
  await page.getByLabel("Route path").fill("/support/triage");
  await page.getByLabel("Deployment").fill("10");
  await page.getByLabel("Auth mode").fill("api_key");
  await page.getByLabel("Allowed origins").fill(frontendOrigin);
  await page.getByLabel("Requests per minute").fill("120");

  await page.getByRole("button", { name: "Validate publish" }).click();
  await expect(page.getByText("Publish validation: valid")).toBeVisible();
  await page.getByRole("button", { name: "Publish surface" }).click();
  await expect(page.getByText("Surface published")).toBeVisible();

  const liveIngress = await page.evaluate(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/v1/ingress/support/triage`, {
      method: "POST",
      headers: {
        Authorization: "Bearer runtime-token",
        "Content-Type": "application/json",
        "X-Request-Id": "req_live_browser_ingress",
      },
      body: JSON.stringify({ ticket_id: "INC-LIVE-BROWSER" }),
    });
    return { status: response.status, body: await response.json() };
  }, apiBaseUrl);
  expect(liveIngress.status).toBe(200);
  expect(liveIngress.body.status).toBe("accepted");

  await page.goto(`/published-surfaces/${setup.surfaceId}`);
  await expect(page.getByText("Exposure health: ready")).toBeVisible();
  await expect(page.getByText("status 200 / trace_")).toBeVisible();

  await page.getByRole("button", { name: "Revoke surface" }).click();
  await page.getByLabel("Danger confirmation").fill(`REVOKE SURFACE ${setup.surfaceId}`);
  await page.getByRole("button", { name: "Confirm revoke" }).click();
  await expect(page.getByText("published_surface.revoke")).toBeVisible();
  await expect(page.getByText("Exposure health: blocked")).toBeVisible();
  await expect(page.getByText("surface_revoked")).toBeVisible();
});

async function createLiveSurface(request: APIRequestContext): Promise<LiveSetup> {
  const login = await request.post(`${apiBaseUrl}/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });
  expect(login.status()).toBe(200);
  const loginBody = await login.json();
  const token = String(loginBody.access_token);
  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Tenant-Id": "1",
    "X-Project-Id": "1",
    "X-Environment": "local",
    "X-Request-Id": "req_live_setup",
  };

  const surface = await request.post(`${apiBaseUrl}/v1/published-surfaces`, {
    headers,
    data: {
      name: "live-browser-support-surface",
      deployment_id: 10,
      type: "http",
      status: "active",
    },
  });
  expect(surface.status()).toBe(201);
  const surfaceBody = await surface.json();
  const surfaceId = Number(surfaceBody.item.id);

  const route = await request.post(`${apiBaseUrl}/v1/ingress-routes`, {
    headers,
    data: {
      name: "live-browser-support-route",
      surface_id: surfaceId,
      path: "/support/triage",
      auth_mode: "api_key",
      status: "active",
    },
  });
  expect(route.status()).toBe(201);
  const routeBody = await route.json();

  return {
    token,
    surfaceId,
    routeId: Number(routeBody.item.id),
  };
}
