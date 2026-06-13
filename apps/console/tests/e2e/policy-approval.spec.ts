import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("simulates, activates, rolls back, and shows policy denied evidence", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/governance/policies");

  await expect(page.getByRole("heading", { name: "Policy workbench" })).toBeVisible();
  await page.getByLabel("Policy name").fill("deny-prod-delete");
  await page.getByLabel("Resource type").fill("deployment");
  await page.getByLabel("Action").fill("delete");
  await page.getByLabel("Decision").selectOption("deny");
  await page.getByLabel("Sample resource id").fill("42");
  await page.getByLabel("Sample environment").fill("prod");
  await page.getByLabel("Audit reason").fill("Block accidental production deletion.");

  await page.getByRole("button", { name: "Simulate policy" }).click();
  await expect(page.getByText("Decision: deny")).toBeVisible();
  await expect(page.getByText("priority_conflict")).toBeVisible();
  await expect(page.getByText("policy.simulate")).toBeVisible();

  await page.getByRole("button", { name: "Activate policy" }).click();
  await expect(page.getByText("Activated version 1")).toBeVisible();
  await expect(page.getByText("Rollback target: version 1")).toBeVisible();
  await expect(page.getByText("Audit comparison")).toBeVisible();
  await expect(page.getByText("decision: deny -> deny")).toBeVisible();

  await page.getByRole("button", { name: "Rollback policy" }).click();
  await expect(page.getByText("Rolled back to version 1")).toBeVisible();

  await page.getByRole("button", { name: "Simulate denied sample" }).click();
  await expect(page.getByText("Policy denied")).toBeVisible();
  await expect(page.getByText("deployment #42")).toBeVisible();
});

test("approves and rejects human tasks with context and resume outcome", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/governance/human-tasks");

  await expect(page.getByRole("heading", { name: "Human Tasks" })).toBeVisible();
  const approveRow = page.getByRole("row", { name: /101/ });
  const rejectRow = page.getByRole("row", { name: /102/ });
  await expect(approveRow.getByText("deploy-bot")).toBeVisible();
  await expect(approveRow.getByText("Policy denied direct production promotion.")).toBeVisible();
  await expect(approveRow.getByText("desired_status: paused -> active")).toBeVisible();
  await expect(approveRow.getByText("Resume: waiting")).toBeVisible();

  await page.getByLabel("Decision comment for task 101").fill("Replay comparison is clean.");
  await page.getByRole("button", { name: "Approve task 101" }).click();
  await expect(approveRow.getByText("Resume: ready")).toBeVisible();
  await expect(approveRow.getByText("Replay comparison is clean.")).toBeVisible();

  await page.getByLabel("Decision comment for task 102").fill("Candidate version has a replay regression.");
  await page.getByRole("button", { name: "Reject task 102" }).click();
  await expect(rejectRow.getByText("Resume: blocked")).toBeVisible();
  await expect(rejectRow.getByText("Candidate version has a replay regression.")).toBeVisible();
});
