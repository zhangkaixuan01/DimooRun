import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("validates model gateway configuration before runtime use", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/governance/model-gateways");

  await expect(page.getByRole("heading", { name: "Model Gateway Workbench" })).toBeVisible();
  await page.getByLabel("Gateway name").fill("primary-openai");
  await page.getByLabel("Credential reference").fill("secret:model-openai");
  await page.getByLabel("Monthly budget").fill("500");
  await page.getByLabel("Fallback gateway").fill("gateway:backup-openai");
  await page.getByRole("button", { name: "Test gateway" }).click();

  await expect(page.getByText("Credential valid")).toBeVisible();
  await expect(page.getByText("Health: ok")).toBeVisible();
  await expect(page.getByText("Budget: $500")).toBeVisible();
  await expect(page.getByText("Fallback: gateway:backup-openai")).toBeVisible();
  await expect(page.getByText("provider_unavailable")).toBeVisible();
  await expect(page.getByText("model_gateway.test")).toBeVisible();

  await page.getByLabel("Credential reference").fill("sk-plaintext");
  await page.getByRole("button", { name: "Test gateway" }).click();
  await expect(page.getByText("credential_ref_must_use_secret_ref")).toBeVisible();
});

test("dry-runs tool schema and approval policy before enabling calls", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/governance/tools");

  await expect(page.getByRole("heading", { name: "Tool Gateway Workbench" })).toBeVisible();
  await page.getByLabel("Tool name").fill("crm.update_ticket");
  await page.getByLabel("Risk level").selectOption("write");
  await page.getByLabel("Tool arguments").fill('{"ticket_id":"T-100","status":"closed"}');
  await page.getByRole("button", { name: "Dry run tool" }).click();

  await expect(page.getByText("Schema valid")).toBeVisible();
  await expect(page.getByText("Risk: write")).toBeVisible();
  await expect(page.getByText("Policy: require_approval")).toBeVisible();
  await expect(page.getByText("Approval: required")).toBeVisible();
  await expect(page.getByRole("link", { name: "Usage history" })).toHaveAttribute("href", "/v1/tools/crm.update_ticket/usage");
});

test("validates and rotates secret references without exposing values", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/governance/secrets");

  await expect(page.getByRole("heading", { name: "Secret Rotation" })).toBeVisible();
  await page.getByLabel("Secret name").fill("model-openai");
  await page.getByLabel("Secret reference").fill("vault://project/model-openai");
  await page.getByLabel("Used by").fill("gateway:primary-openai");
  await page.getByRole("button", { name: "Validate secret" }).click();

  await expect(page.getByText("Secret valid")).toBeVisible();
  await expect(page.getByText("gateway:primary-openai")).toBeVisible();
  await expect(page.getByText("secret.validate")).toBeVisible();
  await expect(page.getByText("secret value", { exact: false })).toHaveCount(0);

  await page.getByLabel("Secret reference").fill("vault://project/model-openai-next");
  await page.getByLabel("Rotation reason").fill("scheduled rotation");
  await page.getByRole("button", { name: "Rotate secret" }).click();

  await expect(page.getByText("Rotated")).toBeVisible();
  await expect(page.getByText("vault://project/model-openai-next")).toBeVisible();
  await expect(page.getByText("secret.rotate")).toBeVisible();
});
