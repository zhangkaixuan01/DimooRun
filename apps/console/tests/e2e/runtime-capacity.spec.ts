import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("shows capacity recommendation and blocked drain guidance for critical attempts", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/capacity");

  await expect(page.getByRole("heading", { name: "Capacity" })).toBeVisible();
  await expect(
    page
      .locator("section.panel")
      .filter({ has: page.getByRole("heading", { name: "Recommended action" }) })
      .getByText("hold_drain"),
  ).toBeVisible();
  await expect(
    page.getByText("Critical attempts are still active. Keep drains blocked until they clear."),
  ).toBeVisible();
});

test("drills from worker health list into worker detail assignments", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/workers?worker=worker_1");

  await expect(page.getByRole("heading", { name: "Workers" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "worker_1" })).toBeVisible();
  await expect(page.getByText("Deployment #10")).toBeVisible();
  await expect(page.getByText("Run #1001")).toBeVisible();
  await expect(
    page.getByText("Drain worker: Worker has active critical attempt and cannot drain safely."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Drain worker" })).toBeDisabled();
});

test("drains a safe worker after confirmation", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/workers?worker=worker_2");

  await expect(page.getByRole("heading", { name: "worker_2" })).toBeVisible();
  await page.getByRole("button", { name: "Drain worker" }).click();
  await expect(page.getByRole("dialog", { name: "Drain worker" })).toBeVisible();
  await page.getByRole("button", { name: "确认" }).click();

  await expect(page.getByText("draining").first()).toBeVisible();
});

test("navigates from a failed agent instance to its worker drilldown", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/agent-instances?instance=901");

  await expect(page.getByRole("heading", { name: "Agent Instances" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Instance #901" })).toBeVisible();
  await expect(page.getByText("provider timeout")).toBeVisible();

  await page.getByRole("link", { name: "worker_1" }).click();

  await expect(page).toHaveURL(/\/runtime\/workers\?worker=worker_1/);
  await expect(page.getByRole("heading", { name: "Workers" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "worker_1" })).toBeVisible();
});

test("phase0l readonly settings", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/platform");

  await expect(page.getByRole("heading", { name: "Platform Settings" })).toBeVisible();
  await expect(
    page.getByText("Production mode keeps organization and project defaults read-only."),
  ).toBeVisible();
  await page.getByRole("heading", { name: "Configuration boundaries" }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("heading", { name: "Configuration boundaries" })).toBeVisible();
  await expect(page.getByText("Organization defaults", { exact: true })).toBeVisible();
  await expect(page.getByText("Project defaults", { exact: true })).toBeVisible();
  await expect(page.getByText("Environment defaults").nth(1)).toBeVisible();
  await expect(page.getByText("default runtime mode")).toBeVisible();

  await page.getByLabel("Deployment strategy").selectOption("blue_green");
  await page.getByRole("button", { name: "Save environment defaults" }).click();

  await expect(page.getByText("Environment defaults updated.")).toBeVisible();
});

test("phase0l provider outage", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/providers");

  await expect(page.getByRole("heading", { name: "Provider Status" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "secret_provider" })).toBeVisible();
  await expect(page.getByText("offline").first()).toBeVisible();
});

test("phase0l preflight blocked", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/danger-zone");

  await expect(page.getByRole("heading", { name: "Danger Zone" })).toBeVisible();
  await page.getByRole("button", { name: "Run preflight" }).click();

  await expect(page.getByText("object_store is not healthy enough for this action.")).toBeVisible();
  await expect(page.getByText("Affected resources")).toBeVisible();
  await expect(page.getByText("Deployments: 2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply dangerous change" })).toBeDisabled();
});

test("phase0l freeze applied", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/danger-zone");

  await page.getByLabel("Action").selectOption("freeze_environment_writes");
  await page.getByRole("button", { name: "Run preflight" }).click();
  await expect(page.getByText("No blocking preflight findings.")).toBeVisible();

  await page.getByLabel("Confirmation").fill("freeze local writes");
  await page.getByRole("button", { name: "Apply dangerous change" }).click();

  await expect(page.getByText("applied")).toBeVisible();
  await expect(page.getByText("Request ID:")).toBeVisible();
  await expect(page.getByText("Environment freeze_writes: true")).toBeVisible();
});
