import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("validates and publishes a governed surface", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/published-surfaces/501");

  await expect(page.getByRole("heading", { name: "Governed Published Surface" })).toBeVisible();
  await expect(page.getByText("Exposure health: ready")).toBeVisible();
  await page.getByLabel("Route path").fill("/support/triage");
  await page.getByLabel("Deployment").fill("10");
  await page.getByLabel("Auth mode").fill("api_key");
  await page.getByLabel("Allowed origins").fill("https://app.example.com");
  await page.getByLabel("Requests per minute").fill("120");
  await page.getByRole("button", { name: "Validate publish" }).click();

  await expect(page.getByText("Publish validation: valid")).toBeVisible();
  await expect(page.getByText("policy_engine: valid")).toBeVisible();
  await page.getByRole("button", { name: "Publish surface" }).click();
  await expect(page.getByText("Surface published")).toBeVisible();
  await expect(page.getByText("published_surface.publish")).toBeVisible();
});

test("blocks invalid publish routes with explicit reasons", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/published-surfaces/501");

  await page.getByLabel("Route path").fill("support");
  await page.getByLabel("Deployment").fill("");
  await page.getByLabel("Auth mode").fill("none");
  await page.getByLabel("Allowed origins").fill("*");
  await page.getByLabel("Requests per minute").fill("0");
  await page.getByRole("button", { name: "Validate publish" }).click();

  await expect(page.getByText("Publish validation: invalid")).toBeVisible();
  await expect(page.getByText("route_path_invalid")).toBeVisible();
  await expect(page.getByText("auth_mode_unsafe")).toBeVisible();
  await expect(page.getByText("deployment_binding_missing")).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish surface" })).toBeDisabled();
});

test("tests a route and drills into the redacted request log", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/published-surfaces/501");

  await page.getByLabel("Synthetic path").fill("/support/triage");
  await page.getByLabel("Synthetic method").fill("POST");
  await page.getByRole("button", { name: "Test route" }).click();

  await expect(page.getByText("Route test: matched")).toBeVisible();
  await expect(page.getByText("auth: allow")).toBeVisible();
  await expect(page.getByText("policy: allow")).toBeVisible();
  await expect(page.getByText("deployment.invoke")).toBeVisible();
  await page.getByRole("button", { name: "Open request log" }).click();
  await expect(page.locator(".request-log-detail").getByText("trace_1", { exact: true })).toBeVisible();
  await expect(page.getByText("authorization: [REDACTED]")).toBeVisible();
  await expect(page.getByText("run_id: 9001")).toBeVisible();
});

test("controls rollout with traffic split, revoke confirmation, and rollback", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/published-surfaces/501");

  await page.getByLabel("Candidate traffic").fill("20");
  await page.getByRole("button", { name: "Apply traffic split" }).click();
  await expect(page.getByText("traffic_split")).toBeVisible();
  await expect(page.getByText("candidate: 20")).toBeVisible();

  await page.getByRole("button", { name: "Revoke surface" }).click();
  await expect(page.getByText("REVOKE SURFACE 501")).toBeVisible();
  await page.getByLabel("Danger confirmation").fill("REVOKE SURFACE 501");
  await page.getByRole("button", { name: "Confirm revoke" }).click();
  await expect(page.getByText("published_surface.revoke")).toBeVisible();
  await expect(page.getByText("Exposure health: blocked")).toBeVisible();
  await expect(page.getByText("surface_revoked")).toBeVisible();

  await page.getByRole("button", { name: "Rollback surface" }).click();
  await expect(page.getByText("rollback", { exact: true })).toBeVisible();
  await expect(page.getByText("rollback_to_version: 1")).toBeVisible();
});
