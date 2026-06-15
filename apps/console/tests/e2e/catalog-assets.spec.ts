import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("creates a governed prompt asset and opens its detail page", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/prompt-assets");

  await expect(page.getByRole("heading", { name: "Prompt Assets", exact: true })).toBeVisible();
  await page.getByLabel("Name").fill("billing-prompt");
  await page.getByLabel("Version").fill("2.0.0");
  await page.getByLabel("Content ref").fill("inline:billing");
  await page.getByRole("button", { name: "Create asset" }).click();

  await expect(page.getByText("Created asset #")).toBeVisible();
  await expect(page.getByText("billing-prompt", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Open" }).first().click();
  await expect(page.getByRole("heading", { name: "billing-prompt", exact: true })).toBeVisible();
});

test("surfaces validation failure and renders version diff for governed assets", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/prompt-assets/813");

  await expect(page.getByRole("heading", { name: "broken-prompt", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Validate asset" }).click();
  await expect(page.getByText("explicit_version_required")).toBeVisible();
  await expect(page.getByText("secret_ref_invalid")).toBeVisible();

  await page.goto("/governance/prompt-assets/811");
  await page.getByRole("link", { name: "Open diff" }).click();
  await expect(page.getByRole("heading", { name: "Version diff", exact: true })).toBeVisible();
  await expect(page.getByText("content_ref")).toBeVisible();
  await expect(page.getByText("inline:triage-v1")).toBeVisible();
  await expect(page.getByText("inline:triage-v2")).toBeVisible();
});

test("approves and publishes a validated asset, blocks deprecate in active use, and rolls back", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/prompt-assets/811");

  await expect(page.getByRole("heading", { name: "support-prompt", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Validate asset" }).click();
  await expect(page.getByText("Validation completed: passed")).toBeVisible();

  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Asset action completed: approve -> approved")).toBeVisible();

  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText("Asset action completed: publish -> published")).toBeVisible();
  await expect(page.getByText("published").first()).toBeVisible();

  await page.goto("/governance/prompt-assets/812");
  await page.getByRole("button", { name: "Deprecate" }).click();
  await expect(page.getByText("Asset is still referenced by an active deployment.")).toBeVisible();

  await page.goto("/governance/prompt-assets/811");
  await page.getByLabel("Rollback target").selectOption("1.0.0");
  await page.getByRole("button", { name: "Rollback" }).click();
  await expect(page).toHaveURL(/\/governance\/prompt-assets\/810$/);
  await expect(page.getByRole("heading", { name: "support-prompt", exact: true })).toBeVisible();
  await expect(page.getByText("v1.0.0 · published", { exact: true })).toBeVisible();
});

test("surfaces catalog item shapes for mcp endpoints, semantic stores, and runtime components", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/governance/catalog-items");

  await expect(page.getByRole("heading", { name: "Catalog Items", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "mcp_endpoint" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "semantic_store" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "runtime_component" })).toBeVisible();

  const runtimeComponentRow = page.getByRole("row", { name: /governed-sandbox/ });
  await runtimeComponentRow.getByRole("link", { name: "Open" }).click();

  await expect(page.getByRole("heading", { name: "governed-sandbox", exact: true })).toBeVisible();
  await expect(page.getByText("Shape · runtime_component")).toBeVisible();
  await expect(page.getByText("Provider · native")).toBeVisible();
  await expect(page.getByText("isolation_level · process")).toBeVisible();
  await expect(page.getByText("active_deployment_dependency")).toBeVisible();
});
