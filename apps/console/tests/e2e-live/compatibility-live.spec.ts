import { expect, test, type APIRequestContext } from "@playwright/test";

const apiBaseUrl = process.env.DIMOORUN_LIVE_API_BASE_URL || "http://127.0.0.1:4180";
const adminEmail = process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun";
const adminPassword = process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345";

async function createLiveSession(request: APIRequestContext): Promise<string> {
  const login = await request.post(`${apiBaseUrl}/v1/auth/login`, {
    data: { email: adminEmail, password: adminPassword },
  });
  expect(login.status()).toBe(200);
  const body = await login.json();
  return String(body.access_token);
}

test("compatibility explorer uses live backend mapping evidence", async ({ page, request }) => {
  const token = await createLiveSession(request);

  await page.addInitScript((sessionToken) => {
    localStorage.setItem("dimoorun.console.locale", "en-US");
    localStorage.setItem("dimoorun.console.token", sessionToken);
  }, token);

  await page.goto("/compatibility");
  await expect(page.getByRole("button", { name: "Generate migration report" })).toBeVisible();

  await page.getByLabel("Capabilities").fill("assistants,threads,runs,hosted_deployments");
  await page.getByRole("button", { name: "Generate migration report" }).click();
  await expect(page.getByText("migration_required", { exact: true })).toBeVisible();
  await expect(page.getByText("Recommended remediation")).toBeVisible();

  await page.getByLabel("Name").fill("compatibility-live");
  await page.getByRole("button", { name: "Create assistant" }).click();
  await expect(page.getByLabel("Assistant ID")).toHaveValue(/assistant_/);

  await page.getByRole("button", { name: "Create thread" }).click();
  await expect(page.getByLabel("Thread ID")).toHaveValue(/thread_/);

  await page.getByLabel("Input message").fill("hello from live compatibility proof");
  await page.getByRole("button", { name: "Create run" }).click();
  await expect(page.getByText("native_task_id")).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});
