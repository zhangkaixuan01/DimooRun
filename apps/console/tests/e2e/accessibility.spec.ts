import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import {
  installConsoleApiMocks,
  seedConsoleSession,
  seedEnglishLocale,
} from "../fixtures/api";

async function expectNoCriticalAxeViolations(page: Page, scope: string = "main") {
  const results = await new AxeBuilder({ page })
    .include(scope)
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const criticalViolations = results.violations.filter((violation) => violation.impact === "critical");

  expect(criticalViolations).toEqual([]);
}

test("dashboard has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await expectNoCriticalAxeViolations(page, "main");
});

test("dense table page has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await expect(page.getByRole("table").first()).toBeVisible();

  await expectNoCriticalAxeViolations(page, "main");
});

test("drawer flow has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page, '[role="dialog"]');
});

test("high-risk confirmation has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Delete" }).first().click();
  await expect(page.getByRole("alertdialog", { name: "Delete Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page, '[role="alertdialog"]');
});

test("deployment task workflow has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");
  await page.getByRole("tab", { name: "Submit via Deployment" }).click();
  await expect(page.getByRole("button", { name: "Submit via Deployment" })).toBeVisible();

  await expectNoCriticalAxeViolations(page, "main");
});

test("run detail diagnostics page has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runs/1001");
  await expect(page.getByText("Event Timeline")).toBeVisible();

  await expectNoCriticalAxeViolations(page, "main");
});

test("mobile agent drawer has no critical accessibility violations", async ({ page }) => {
  test.slow();
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 375, height: 812 });

  await page.goto("/agents");
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();

  await expectNoCriticalAxeViolations(page, '[role="dialog"]');
});

test("shared drawer closes on Escape and restores keyboard workflow", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Register Agent" })).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Register Agent" })).toBeFocused();
});

test("shared data table supports keyboard row selection", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");
  const firstRow = page.locator("tbody tr").first();
  await firstRow.focus();
  await page.keyboard.press("Enter");

  await expect(page.getByRole("heading", { name: /Deployment #/ })).toBeVisible();
});
