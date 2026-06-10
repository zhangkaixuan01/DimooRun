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
