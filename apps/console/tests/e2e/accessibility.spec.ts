import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

async function expectNoCriticalAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const criticalViolations = results.violations.filter((violation) => violation.impact === "critical");

  expect(criticalViolations).toEqual([]);
}

test("dashboard has no critical accessibility violations", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "仪表盘" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("dense table page has no critical accessibility violations", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await expect(page.getByRole("table").first()).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("drawer flow has no critical accessibility violations", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "注册智能体" }).click();
  await expect(page.getByRole("dialog", { name: "注册智能体" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});

test("high-risk confirmation has no critical accessibility violations", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "删除" }).first().click();
  await expect(page.getByRole("alertdialog", { name: "删除智能体" })).toBeVisible();

  await expectNoCriticalAxeViolations(page);
});
