import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import {
  installConsoleApiMocks,
  seedConsoleSession,
  seedEnglishLocale,
} from "../fixtures/api";

async function expectNoCriticalAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const criticalViolations = results.violations.filter((violation) => violation.impact === "critical");

  expect(criticalViolations).toEqual([]);
}

test("dashboard has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("dense table page has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await expect(page.getByRole("table").first()).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("drawer flow has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("high-risk confirmation has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByRole("alertdialog", { name: "Delete Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("deployment task workflow has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");
  await page.getByRole("tab", { name: "Submit via Deployment" }).click();
  await expect(page.getByRole("button", { name: "Submit via Deployment" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("run detail diagnostics page has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runs/1001");
  await expect(page.getByText("Event Timeline")).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("mobile agent drawer has no critical accessibility violations", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 375, height: 812 });

  await page.goto("/agents");
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});
