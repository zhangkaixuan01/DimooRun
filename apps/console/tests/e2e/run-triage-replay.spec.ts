import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("triages a failed run and opens replay comparison evidence", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/runs/1001/triage");

  await expect(page.getByRole("heading", { name: "Run triage #1001" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "provider timeout" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Timeline" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Attempts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Audit evidence" })).toBeVisible();

  await page.getByRole("link", { name: "Compare replay" }).click();
  await expect(page).toHaveURL(/\/replay\/compare\?source_run_id=1001/);
  await expect(page.getByRole("heading", { name: "Replay comparison" })).toBeVisible();
});

test("creates replay comparison, saves dataset evidence, and keeps source immutable", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/replay/compare?source_run_id=1001");

  await expect(page.getByRole("heading", { name: "Replay comparison" })).toBeVisible();
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByLabel("Replay config").fill('{"temperature":0,"dataset_label":"incident-triage"}');
  await page.getByRole("button", { name: "Create comparison" }).click();

  await expect(page.getByText("Comparison #cmp-1001-12")).toBeVisible();
  await expect(page.getByText("Source run #1001")).toBeVisible();
  await expect(page.getByText("Replay run #2001")).toBeVisible();
  await expect(page.getByText("Error changed")).toBeVisible();
  await expect(page.getByText("Source remains immutable", { exact: true })).toBeVisible();

  await page.getByLabel("Dataset name").fill("support-regressions");
  await page.getByLabel("Dataset label").fill("provider-timeout");
  await page.getByRole("button", { name: "Save evidence" }).click();

  await expect(page.getByText("Saved evidence to support-regressions")).toBeVisible();
  await expect(page.getByText("source_run_id: 1001")).toBeVisible();
  await expect(page.getByText("replay_run_id: 2001")).toBeVisible();
});
