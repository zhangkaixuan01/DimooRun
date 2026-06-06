import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("acknowledges and resolves an incident with evidence and delivery attempts", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/ops/incidents");

  await expect(page.getByRole("heading", { name: "Incident Triage" })).toBeVisible();
  await page.getByLabel("Incident").fill("201");
  await page.getByLabel("Linked run").fill("1001");
  await page.getByLabel("Linked task").fill("8001");
  await page.getByLabel("Linked event").fill("evt-1001-attempt");
  await page.getByLabel("Notification channel").fill("pagerduty-primary");
  await page.getByLabel("Audit note").fill("Escalated provider outage.");
  await page.getByRole("button", { name: "Acknowledge incident" }).click();

  await expect(page.getByText("Incident #201 acknowledged")).toBeVisible();
  await expect(page.getByText("run: 1001")).toBeVisible();
  await expect(page.getByText("task: 8001")).toBeVisible();
  await expect(page.getByText("event: evt-1001-attempt")).toBeVisible();
  await expect(page.getByText("delivery: sent")).toBeVisible();
  await expect(page.getByText("incident.acknowledge")).toBeVisible();

  await page.getByLabel("Resolution summary").fill("Rerouted traffic to healthy gateway.");
  await page.getByRole("button", { name: "Resolve incident" }).click();
  await expect(page.getByText("Incident #201 resolved")).toBeVisible();
  await expect(page.getByText("incident.resolve")).toBeVisible();
});

test("sends a notification probe and exposes the delivery attempt", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/ops/incidents");

  await page.getByRole("spinbutton", { name: "Channel", exact: true }).fill("55");
  await page.getByLabel("Channel name").fill("pagerduty-primary");
  await page.getByLabel("Target ref").fill("pd://service/runtime");
  await page.getByLabel("Probe message").fill("Synthetic notification probe");
  await page.getByRole("button", { name: "Send test notification" }).click();

  await expect(page.getByText("Notification probe sent")).toBeVisible();
  await expect(page.getByText("visible_to_operator: true")).toBeVisible();
  await expect(page.getByText("notification.test_send")).toBeVisible();
});

test("previews backup and restore dry runs with destructive restore guardrails", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/ops/recovery");

  await expect(page.getByRole("heading", { name: "Backup And Restore" })).toBeVisible();
  await page.getByLabel("Backup plan").fill("9");
  await page.getByLabel("Backup targets").fill("runs,datasets,audit_logs");
  await page.getByLabel("Storage ref").fill("s3://dimoorun-backups/local");
  await page.getByRole("button", { name: "Preview backup" }).click();

  await expect(page.getByText("Backup dry-run ready")).toBeVisible();
  await expect(page.getByText("tenant_id: 1")).toBeVisible();
  await expect(page.getByText("backup.dry_run")).toBeVisible();

  await page.getByLabel("Backup ref").fill("backup://2026-06-05/project");
  await page.getByLabel("Restore targets").fill("runs");
  await page.getByLabel("Destructive restore").check();
  await page.getByLabel("Confirmation").fill("restore");
  await page.getByRole("button", { name: "Preview restore" }).click();

  await expect(page.getByText("destructive_restore_confirmation_required")).toBeVisible();
  await expect(page.getByText("RESTORE PROJECT 1")).toBeVisible();

  await page.getByLabel("Confirmation").fill("RESTORE PROJECT 1");
  await page.getByRole("button", { name: "Preview restore" }).click();
  await expect(page.getByText("Restore dry-run ready")).toBeVisible();
  await expect(page.getByText("restore.dry_run")).toBeVisible();
});
