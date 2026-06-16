import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("semantic store providers page validates provider readiness", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/semantic-store");

  await expect(page.getByRole("heading", { name: "Semantic Store Providers" })).toBeVisible();
  await page.getByRole("button", { name: "Validate provider" }).first().click();
  await expect(page.locator("dt", { hasText: "provider status" })).toBeVisible();
  await expect(page.locator("dt", { hasText: "index coverage" })).toBeVisible();
});

test("sandbox policies page previews enforcement result before save", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/sandbox-policies");

  await expect(page.getByRole("heading", { name: "Sandbox Policies" })).toBeVisible();
  await page.getByRole("button", { name: "Preview enforcement" }).first().click();
  await expect(page.getByText("blocked capabilities")).toBeVisible();
  await expect(page.getByText("audit reason required")).toBeVisible();
});

test("container pool policies page estimates capacity impact", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/container-pool-policies");

  await expect(page.getByRole("heading", { name: "Container Pool Policies" })).toBeVisible();
  await page.getByRole("button", { name: "Estimate impact" }).first().click();
  await expect(page.getByText("warm capacity")).toBeVisible();
  await expect(page.getByText("scale limit")).toBeVisible();
});
