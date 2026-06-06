import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("previews promotion impact, promotes a candidate, and rolls back", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");

  await expect(page.getByRole("heading", { name: "部署" })).toBeVisible();
  await page.getByRole("tab", { name: "Promotion" }).click();
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByRole("button", { name: "Preview promotion" }).click();

  await expect(page.getByRole("heading", { name: "Impact preview" })).toBeVisible();
  await expect(page.getByText("Active runs")).toBeVisible();
  await expect(page.locator("dd", { hasText: /^2$/ }).first()).toBeVisible();
  await expect(page.getByText("Rollback target")).toBeVisible();
  await expect(page.locator("dd", { hasText: /^11$/ }).first()).toBeVisible();
  await expect(page.getByText("queued_tasks_will_use_current_version")).toBeVisible();

  await page.getByLabel("Rollout reason").fill("ship validated support improvements");
  await page.getByRole("button", { name: "Promote candidate" }).click();

  await expect(page.getByText("Promoted to version 12")).toBeVisible();
  await expect(page.getByText("11 -> 12")).toBeVisible();

  await page.getByLabel("Rollback reason").fill("candidate regression");
  await page.getByRole("button", { name: "Rollback" }).click();

  await expect(page.getByText("Rolled back to version 11")).toBeVisible();
});

test("confirms pause and resume controls with audit impact", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");

  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(page.getByText("AuditLog", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认" }).click();
  await expect(page.getByText("paused").first()).toBeVisible();

  await page.getByRole("button", { name: "恢复", exact: true }).click();
  await expect(page.getByText("AuditLog", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认" }).click();
  await expect(page.getByText("active").first()).toBeVisible();
});

test("surfaces policy denial and stale deployment conflicts during promotion", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/deployments");

  await page.getByRole("tab", { name: "Promotion" }).click();
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByRole("button", { name: "Preview promotion" }).click();

  await page.getByLabel("Rollout reason").fill("policy freeze");
  await page.getByRole("button", { name: "Promote candidate" }).click();
  await expect(page.getByText("policy_denied")).toBeVisible();
  await expect(page.getByText("production freeze")).toBeVisible();

  await page.getByLabel("Rollout reason").fill("stale operator tab");
  await page.getByRole("button", { name: "Promote candidate" }).click();
  await expect(page.getByText("deployment_version_conflict")).toBeVisible();
  await expect(page.getByText("Deployment version changed after the promotion workflow was prepared.")).toBeVisible();
});
