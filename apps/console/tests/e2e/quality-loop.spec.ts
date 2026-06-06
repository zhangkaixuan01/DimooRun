import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("captures a failed run into a redacted dataset item", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/observability/datasets");

  await expect(page.getByRole("heading", { name: "Dataset Capture" })).toBeVisible();
  await page.getByLabel("Dataset name").fill("support-regressions");
  await page.getByLabel("Source run").fill("1001");
  await page.getByLabel("Dataset label").fill("provider-timeout");
  await page.getByLabel("Redact fields").fill("api_key");
  await page.getByRole("button", { name: "Capture run" }).click();

  await expect(page.getByText("Captured dataset item #301")).toBeVisible();
  await expect(page.getByText("source_run_id: 1001")).toBeVisible();
  await expect(page.getByText("api_key: [REDACTED]")).toBeVisible();
  await expect(page.getByText("dataset.capture_run")).toBeVisible();

  await page.getByRole("button", { name: "Capture run" }).click();
  await expect(page.getByText("Duplicate item reused")).toBeVisible();
});

test("runs an experiment and shows the passed quality gate", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/observability/experiments");

  await expect(page.getByRole("heading", { name: "Experiment Workbench" })).toBeVisible();
  await page.getByLabel("Experiment name").fill("candidate-quality");
  await page.getByLabel("Dataset").fill("21");
  await page.getByLabel("Candidate version").fill("12");
  await page.getByLabel("Minimum score").fill("0.8");
  await page.getByRole("button", { name: "Run experiment" }).click();

  await expect(page.getByText("Experiment run #401")).toBeVisible();
  await expect(page.getByText("Average score: 1")).toBeVisible();
  await expect(page.getByText("Quality gate: passed")).toBeVisible();
  await expect(page.getByText("Promotion: allowed")).toBeVisible();
  await expect(page.getByText("exact_match")).toBeVisible();
});

test("previews failed and passed promotion quality gates", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/observability/quality-gate");

  await expect(page.getByRole("heading", { name: "Quality Gate" })).toBeVisible();
  await page.getByLabel("Deployment").fill("10");
  await page.getByLabel("Candidate version").fill("12");
  await page.getByLabel("Experiment run").fill("402");
  await page.getByRole("button", { name: "Preview gate" }).click();

  await expect(page.getByText("Quality gate: failed")).toBeVisible();
  await expect(page.getByText("Promotion: blocked")).toBeVisible();
  await expect(page.getByText("quality_gate_failed")).toBeVisible();
  await expect(page.getByText("quality_gate.preview")).toBeVisible();

  await page.getByLabel("Experiment run").fill("401");
  await page.getByRole("button", { name: "Preview gate" }).click();
  await expect(page.getByText("Quality gate: passed")).toBeVisible();
  await expect(page.getByText("Promotion: allowed")).toBeVisible();
});
