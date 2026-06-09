import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("explores compatibility migration and runtime mapping", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/compatibility");

  await expect(page.getByRole("heading", { name: "Compatibility", exact: true })).toBeVisible();
  await page.getByLabel("Capabilities").fill("assistants,threads,runs,hosted_deployments");
  await page.getByRole("button", { name: "Generate migration report" }).click();

  await expect(page.getByText("migration_required")).toBeVisible();
  await expect(page.getByText("hosted_deployments: compatibility_not_supported")).toBeVisible();
  await expect(page.getByText("supports_last_event_id_replay")).toBeVisible();

  await page.getByLabel("Name").fill("support-agent");
  await page.getByRole("button", { name: "Create assistant" }).click();
  await expect(page.getByRole("button", { name: "support-agent" })).toBeVisible();
  await expect(page.getByLabel("Assistant ID")).toHaveValue("assistant_1");

  await page.getByLabel("Metadata label").fill("migration-check");
  await page.getByRole("button", { name: "Create thread" }).click();
  await expect(page.getByLabel("Thread ID")).toHaveValue("thread_1");

  await page.getByLabel("Assistant ID").fill("assistant_1");
  await page.getByLabel("Thread ID").fill("thread_1");
  await page.getByLabel("Input message").fill("hello from compatibility explorer");
  await page.getByRole("button", { name: "Create run" }).click();
  await expect(page.getByRole("link", { name: "Run #3101" })).toBeVisible();
  await page.getByLabel("Run ID").fill("3101");
  await page.getByRole("button", { name: "Join run" }).click();
  await expect(page.getByText('"compat_status": "succeeded"')).toBeVisible();

  await page.getByRole("button", { name: "Stream probe" }).click();
  await expect(page.getByText("run.created (3102:1)")).toBeVisible();
  await expect(page.getByText("run.started (3102:3)")).toBeVisible();
  await expect(page.getByText("stream_mode")).toBeVisible();
  await page.getByLabel("Run ID").fill("3102");
  await expect(page).toHaveURL(/thread_id=thread_1/);
  await expect(page).toHaveURL(/run_id=3102/);
  await expect(page).toHaveURL(/last_event_id=3102%3A1/);
  await page.reload();
  await expect(page.getByLabel("Thread ID")).toHaveValue("thread_1");
  await expect(page.getByLabel("Run ID")).toHaveValue("3102");
  await expect(page.getByLabel("Last-Event-ID")).toHaveValue("3102:1");
  await page.getByRole("button", { name: "Load stream status" }).click();
  await expect(page.getByText("latest_event_id: 3102:3 / replay_from: 3102:1")).toBeVisible();
  await expect(page.getByText("supports_last_event_id_replay")).toBeVisible();
  await page.getByLabel("Last-Event-ID").fill("3102:1");
  await page.getByRole("button", { name: "Replay events" }).click();
  await expect(page.getByText("task.queued (3102:2)")).toBeVisible();
  await expect(page.getByText("replayed_event_types")).toBeVisible();
  await page.getByRole("button", { name: "Cancel run" }).click();
  await expect(page.getByText('"compat_status": "cancelled"')).toBeVisible();
});
