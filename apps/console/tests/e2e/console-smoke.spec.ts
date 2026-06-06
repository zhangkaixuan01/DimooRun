import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("redirects anonymous users to the login page", async ({ page }) => {
  await page.goto("/dashboard");

  await expect(page).toHaveURL(/\/login\?redirect=\/dashboard$/);
  await expect(page.getByRole("heading", { name: "登录" })).toBeVisible();
  await expect(page.getByLabel("邮箱")).toHaveValue("admin@local.dimoorun");
});

test("renders the authenticated dashboard shell", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.goto("/dashboard");

  await expect(page.getByRole("link", { name: /DimooRun/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "仪表盘" })).toBeVisible();
  await expect(page.getByText(/API 模式:/)).toBeVisible();
  await expect(page.getByRole("link", { name: /智能体/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /部署/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "暂停刷新" })).toBeVisible();
  await expect(page.getByText("E2E Operator")).toBeVisible();
});

test("keeps the login page free of critical accessibility violations", async ({ page }) => {
  await page.goto("/login");

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const criticalViolations = results.violations.filter((violation) => violation.impact === "critical");

  expect(criticalViolations).toEqual([]);
});
