import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("previews effective role permission impact before save", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/roles-permissions");

  await expect(page.getByRole("heading", { name: "Role Permission Matrix" })).toBeVisible();
  await page.locator(".permission-row", { hasText: "run:read" }).getByRole("checkbox").uncheck();
  await page.getByRole("button", { name: "Preview impact" }).click();

  await expect(page.getByText(/removed:\s*run:read/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Affected operators" })).toBeVisible();
  await expect(page.locator(".impact-row").getByText("E2E Operator")).toBeVisible();
});

test("blocks self-lockout role changes before apply", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/roles-permissions");

  await page.locator(".permission-row", { hasText: "identity:role:write" }).getByRole("checkbox").uncheck();
  await page.getByRole("button", { name: "Preview impact" }).click();

  await expect(
    page.getByText(/Current operator cannot apply a role change/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Apply matrix" })).toBeDisabled();
});

test("revokes an operator session from the detail view", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/operators/2");

  await expect(page.getByRole("heading", { name: "User Access Detail" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Reviewer" })).toBeVisible();
  await page.getByRole("button", { name: "Revoke session" }).first().click();

  const sessionsPanel = page.locator("section.panel").filter({ has: page.getByRole("heading", { name: "Active sessions" }) });
  await expect(sessionsPanel.locator("tbody tr")).toHaveCount(1);
});

test("rotates a service account key and shows the one-time secret", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/service-accounts/301");

  await expect(page.getByRole("heading", { name: "Service Account Detail" })).toBeVisible();
  await page.getByRole("button", { name: "Rotate" }).first().click();
  await page.getByLabel("Audit reason").fill("Routine key rotation");
  await page.getByRole("button", { name: "Rotate key" }).click();

  await expect(page.getByText("One-time secret")).toBeVisible();
  await expect(page.getByText("dmr_rotated_secret_702")).toBeVisible();
});
