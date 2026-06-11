import { expect, test, type Page, type TestInfo } from "@playwright/test";

import {
  installConsoleApiMocks,
  seedConsoleSession,
  seedEnglishLocale,
} from "../fixtures/api";

async function attachScreenshot(page: Page, testInfo: TestInfo, name: string) {
  const path = testInfo.outputPath(name);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: "image/png" });
}

test("captures desktop workflow screenshots for dashboard and run detail", async ({ page }, testInfo) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 1440, height: 1080 });

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await attachScreenshot(page, testInfo, "dashboard-desktop.png");

  await page.goto("/runs/1001");
  await expect(page.getByText("Event Timeline")).toBeVisible();
  await attachScreenshot(page, testInfo, "run-detail-desktop.png");
});

test("captures mobile workflow screenshots for agent and deployment flows", async ({ page }, testInfo) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 375, height: 812 });

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();
  await attachScreenshot(page, testInfo, "agents-mobile-drawer.png");

  await page.goto("/deployments");
  await expect(page.getByRole("heading", { name: "Deployments" })).toBeVisible();
  await page.getByRole("tab", { name: "Submit via Deployment" }).click();
  await expect(page.getByRole("button", { name: "Submit via Deployment" })).toBeVisible();
  await attachScreenshot(page, testInfo, "deployment-task-mobile.png");
});
