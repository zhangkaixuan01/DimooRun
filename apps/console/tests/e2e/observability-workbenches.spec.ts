import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("audit log workbench filters by actor and opens linked evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/audit-logs");

  await expect(page.getByRole("heading", { name: "Audit Log Workbench" })).toBeVisible();
  await page.getByLabel("Actor").fill("operator");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByText("policy.activate")).toBeVisible();
  await page.getByRole("button", { name: "Open evidence" }).first().click();
  await expect(page.getByRole("dialog", { name: "Audit evidence" })).toBeVisible();
});

test("artifact workbench previews metadata and links back to run", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/artifacts");

  await expect(page.getByRole("heading", { name: "Artifact Workbench" })).toBeVisible();
  await page.getByRole("button", { name: "Inspect artifact" }).first().click();
  await expect(page.getByRole("dialog", { name: "Artifact detail" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});

test("evaluation workbench compares passed and failed results", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/evaluations");

  await expect(page.getByRole("heading", { name: "Evaluation Workbench" })).toBeVisible();
  await expect(page.getByText("Pass rate")).toBeVisible();
  await page.getByRole("button", { name: "Open result" }).first().click();
  await expect(page.getByRole("dialog", { name: "Evaluation result" })).toBeVisible();
});

test("feedback workbench triages user feedback against run evidence", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/feedback");

  await expect(page.getByRole("heading", { name: "Feedback Workbench" })).toBeVisible();
  await page.getByLabel("Sentiment").selectOption("negative");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.getByRole("button", { name: "Open feedback" }).first().click();
  await expect(page.getByRole("dialog", { name: "Feedback detail" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Run #/ })).toBeVisible();
});

test("replay jobs workbench exposes status, source run, and retry action", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/observability/replay-jobs");

  await expect(page.getByRole("heading", { name: "Replay Jobs Workbench" })).toBeVisible();
  await expect(page.getByText("Source run")).toBeVisible();
  await page.getByRole("button", { name: "Inspect replay job" }).first().click();
  await expect(page.getByRole("dialog", { name: "Replay job detail" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry replay" })).toBeVisible();
});
