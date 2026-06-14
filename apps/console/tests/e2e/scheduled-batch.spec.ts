import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("previews schedules, surfaces invalid timezone, and drives pause resume trigger", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/schedules");

  await expect(page.getByRole("heading", { name: "Scheduled Runs", exact: true })).toBeVisible();
  await page.getByLabel("Timezone").fill("Mars/Phobos");
  await page.getByRole("button", { name: "Preview schedule" }).click();
  await expect(page.getByText("invalid_timezone")).toBeVisible();

  await page.getByLabel("Timezone").fill("UTC");
  await page.getByLabel("Missed-run policy").selectOption("catch_up");
  await page.getByRole("button", { name: "Preview schedule" }).click();
  await expect(
    page.locator("form").getByText("next fire: 2026-06-13T01:30:00.000Z", { exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Create schedule" }).click();
  await expect(page.getByText("Schedule #1203 created.")).toBeVisible();

  await page.getByRole("button", { name: "Pause schedule" }).click();
  await expect(page.getByText("Schedule paused.")).toBeVisible();
  await expect(page.getByText("maintenance").first()).toBeVisible();

  await page.getByRole("button", { name: "Resume schedule" }).click();
  await expect(page.getByText("Schedule resumed.")).toBeVisible();

  await page.getByRole("button", { name: "Trigger schedule" }).click();
  await expect(page.getByText("Triggered Run #9001.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Run #9001" })).toBeVisible();
  await expect(page.getByText("last trigger source: manual")).toBeVisible();
  await expect(page.getByText("last task status: queued")).toBeVisible();
  await expect(page.getByText("Trigger count")).toBeVisible();
});

test("creates batch runs, shows partial failure drilldown, and cancels queued items", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/runtime/batches");

  await expect(page.getByRole("heading", { name: "Batch Runs", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "backfill-failed-runs", exact: true })).toBeVisible();
  await expect(page.getByText("batch_item_invalid")).toBeVisible();
  await expect(page.getByText("Retrying").first()).toBeVisible();
  await expect(page.getByText("retrying 1").first()).toBeVisible();

  await page.getByRole("button", { name: "Create batch" }).click();
  await expect(page.getByText("Batch #1302 created.")).toBeVisible();
  await expect(page.getByText("queued 2").first()).toBeVisible();

  await page.getByRole("button", { name: "Cancel batch" }).click();
  await expect(page.getByRole("alertdialog", { name: "Cancel batch" })).toBeVisible();
  await page.getByRole("button", { name: "确认" }).click();

  await expect(page.getByText("Batch cancelled.")).toBeVisible();
  const batchSummary = page.locator(".detail-panel .summary");
  await expect(batchSummary.getByText("Cancelled items")).toBeVisible();
  await expect(batchSummary.getByText("2", { exact: true })).toBeVisible();
});
