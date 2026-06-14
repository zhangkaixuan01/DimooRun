import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("shows cost breakdown and anomaly drilldown", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/costs");

  await expect(page.getByRole("heading", { name: "Cost", exact: true })).toBeVisible();
  const breakdownTable = page.locator("table").first();
  await expect(breakdownTable.getByText("Deployment #10", { exact: true })).toBeVisible();
  await expect(breakdownTable.getByRole("cell", { name: "$1.90" })).toBeVisible();
  await expect(breakdownTable.getByText("passed", { exact: true })).toBeVisible();
  await expect(breakdownTable.getByText("exp #401", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Deployment spend spike/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Deployment #10" })).toBeVisible();

  await page.getByLabel("Group by").selectOption("provider");
  await expect(page.getByText("anthropic", { exact: true }).first()).toBeVisible();
});

test("saves and reapplies a persisted cost view", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/costs");

  await page.getByLabel("Group by").selectOption("provider");
  await page.getByLabel("Time range").selectOption("90");
  await page.getByLabel("View name").fill("provider regression watch");
  await page.getByRole("button", { name: "Save current view" }).click();

  await expect(page.getByText("provider regression watch", { exact: true })).toBeVisible();
  await page.getByLabel("Group by").selectOption("deployment");
  await page.getByRole("button", { name: "Apply" }).first().click();

  await expect(page.getByRole("cell", { name: "openai" }).first()).toBeVisible();
  await expect(page.getByLabel("View name")).toHaveValue("provider regression watch");
});

test("previews budget impact and top contributors", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/budgets");

  await expect(page.getByRole("heading", { name: "Budget", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Preview budget policy" }).click();

  await expect(page.getByText("Projected spend")).toBeVisible();
  await expect(page.getByText("Notification preview -> slack:#ops-finops")).toBeVisible();
  await expect(page.getByText("Action preview -> require_approval")).toBeVisible();
  await expect(page.getByText("Deployment #10")).toBeVisible();
});

test("saves a budget policy and previews the persisted guardrail", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/budgets");

  await page.getByLabel("Name").fill("staging guardrail");
  await page.getByRole("button", { name: "Save policy" }).click();

  await expect(page.getByRole("button", { name: /staging guardrail/ })).toBeVisible();
  await expect(page.getByText("Saved policy: staging guardrail")).toBeVisible();
  await expect(page.getByText("Notification preview -> slack:#ops-finops")).toBeVisible();
});

test("surfaces blocked budget preview without policy update permission", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/budgets");

  await page.getByLabel("Notification channel").selectOption("902");
  await page.getByRole("button", { name: "Preview budget policy" }).click();

  await expect(page.getByText("policy_update_required")).toBeVisible();
  await expect(page.getByText("Missing permission: policy:update")).toBeVisible();
});
