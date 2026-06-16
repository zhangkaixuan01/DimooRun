import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("organization scope page shows active tenant, project, and switch evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/identity/scopes");

  await expect(page.getByRole("heading", { name: "Organization Scope" })).toBeVisible();
  await expect(page.getByText("Active tenant")).toBeVisible();
  await expect(page.getByText("Active project")).toBeVisible();
  await page.getByRole("button", { name: "Preview switch" }).click();
  const dialog = page.getByRole("dialog", { name: "Scope switch preview" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("affected runs", { exact: true })).toBeVisible();
  await expect(dialog.getByText("affected deployments", { exact: true })).toBeVisible();
});

test("policies page exposes policy simulation without generic crud residue", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/policies");

  await expect(page.getByRole("heading", { name: "Policy Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Simulate policy" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Policy simulation" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("Decision:", { exact: false })).toBeVisible();
  await expect(dialog.getByText("Matched rule:", { exact: false })).toBeVisible();
});

test("config and template assets expose version evidence and promotion actions", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/config-assets");
  await expect(page.getByRole("heading", { name: "Config Assets" })).toBeVisible();
  await page.getByRole("link", { name: "Open asset" }).first().click();
  await expect(page.getByText("Version evidence")).toBeVisible();
  await expect(page.getByRole("button", { name: "Promote version" })).toBeVisible();

  await page.goto("/governance/template-assets");
  await expect(page.getByRole("heading", { name: "Template Assets" })).toBeVisible();
  await page.getByRole("link", { name: "Open template" }).first().click();
  await expect(page.getByText("Version evidence")).toBeVisible();
  await expect(page.getByRole("button", { name: "Promote version" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Rollback version" })).toBeVisible();
});
