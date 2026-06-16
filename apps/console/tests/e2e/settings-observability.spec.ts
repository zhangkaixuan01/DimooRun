import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("observability exporter workbench validates OTLP target and shows proof state", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/settings/observability-exporters");

  await expect(page.getByRole("heading", { name: "Observability Exporters" })).toBeVisible();
  await page.getByRole("button", { name: "Validate exporter" }).first().click();
  await expect(page.getByText("validation status")).toBeVisible();
  await expect(page.getByText("last proof")).toBeVisible();
});
