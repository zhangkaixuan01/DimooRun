import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("runs the P0-B golden operator evidence path", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/agents");
  await page.getByRole("button", { name: "Open trust evidence" }).first().click();
  const trustDialog = page.getByRole("dialog", { name: "Package trust evidence" });
  await expect(trustDialog.getByText("tok_support_100", { exact: true })).toBeVisible();
  await expect(trustDialog.getByText("sha256:111111-support", { exact: true })).toBeVisible();
  await expect(trustDialog.getByText("verified", { exact: true })).toBeVisible();
  await expect(trustDialog.getByText("available", { exact: true })).toBeVisible();
  await expect(trustDialog.getByText("network-egress-llm-only", { exact: true })).toBeVisible();

  await page.goto("/runs/1001");
  await expect(page.getByRole("heading", { name: "Operator evidence path" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Triage run/ })).toHaveAttribute("href", "/runs/1001/triage");
  await expect(page.getByRole("link", { name: /Compare replay/ })).toHaveAttribute("href", "/replay/compare?source_run_id=1001");
  await expect(page.getByRole("link", { name: /Approval/ })).toHaveAttribute("href", "/governance/human-tasks?run_id=1001");
  await expect(page.getByRole("link", { name: /Rollback/ })).toHaveAttribute("href", "/deployments/10?tab=promotion");
  await expect(page.getByRole("link", { name: /Audit Logs Filter audit evidence/ })).toHaveAttribute("href", "/observability/audit-logs?run_id=1001");

  await page.getByRole("link", { name: /Triage run/ }).click();
  await expect(page).toHaveURL(/\/runs\/1001\/triage/);
  await expect(page.getByRole("heading", { name: "Run triage #1001" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Golden operator demo" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "provider timeout" })).toBeVisible();

  await page.getByRole("link", { name: "Compare replay", exact: true }).click();
  await expect(page).toHaveURL(/\/replay\/compare\?source_run_id=1001/);
  await expect(page.getByRole("heading", { name: "Replay comparison" })).toBeVisible();
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByLabel("Replay config").fill('{"temperature":0,"dataset_label":"incident-triage"}');
  await page.getByRole("button", { name: "Create comparison" }).click();
  await expect(page.getByText("Comparison #cmp-1001-12")).toBeVisible();
  await expect(page.getByText("Replay run #2001")).toBeVisible();
  await expect(page.getByText("Error changed")).toBeVisible();
  await page.getByLabel("Dataset name").fill("support-regressions");
  await page.getByLabel("Dataset label").fill("provider-timeout");
  await page.getByRole("button", { name: "Save evidence" }).click();
  await expect(page.getByText("Saved evidence to support-regressions")).toBeVisible();

  await page.goto("/governance/human-tasks?run_id=1001");
  await expect(page.getByRole("heading", { name: "Human Tasks" })).toBeVisible();
  const approvalRow = page.getByRole("row", { name: /101/ });
  await expect(approvalRow.getByText("Resume: waiting")).toBeVisible();
  await page.getByLabel("Decision comment for task 101").fill("Replay comparison is clean.");
  await page.getByRole("button", { name: "Approve task 101" }).click();
  await expect(approvalRow.getByText("Resume: ready")).toBeVisible();

  await page.goto("/deployments/10?tab=promotion");
  await expect(page.getByRole("heading", { name: "Deployments", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Promotion" })).toHaveAttribute("aria-selected", "true");
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByLabel("Experiment run").fill("401");
  await page.getByRole("button", { name: "Preview promotion" }).click();
  await expect(page.getByRole("heading", { name: "Impact preview" })).toBeVisible();
  await expect(page.getByText("Quality gate: passed")).toBeVisible();
  await page.getByLabel("Rollout reason").fill("ship validated support improvements");
  await page.getByRole("button", { name: "Promote candidate" }).click();
  await expect(page.getByText("Promoted to version 12")).toBeVisible();
  await page.getByLabel("Rollback reason").fill("candidate regression");
  await page.getByRole("button", { name: "Rollback" }).click();
  await expect(page.getByText("Rolled back to version 11")).toBeVisible();

  await page.goto("/observability/audit-logs?run_id=1001");
  await expect(page.getByRole("heading", { name: "Audit Log Workbench" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Run" })).toHaveValue("1001");
  await expect(page.getByRole("cell", { name: "Run #1001" })).toBeVisible();
  await expect(page.getByText("policy.activate")).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export audit evidence" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("dimoorun-audit-evidence-run-1001.json");
  const path = await download.path();
  if (!path) throw new Error("Expected local audit evidence download path");
  const payload = JSON.parse(readFileSync(path, "utf8")) as {
    filters: { run_id: string };
    count: number;
    items: Array<{ run_id: number; action: string }>;
  };
  expect(payload.filters.run_id).toBe("1001");
  expect(payload.count).toBeGreaterThan(0);
  expect(payload.items.some((item) => item.run_id === 1001 && item.action === "policy.activate")).toBe(true);
});
