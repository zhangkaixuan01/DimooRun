import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

test("validates a package and creates a ready version from the validated result", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/packages/register");

  await expect(page.getByRole("heading", { name: "Package Registration" })).toBeVisible();
  await page.getByLabel("Package URI").fill("oci://registry.local/support-agent:1.0.0");
  await page.getByLabel("Entrypoint").fill("agent:create_agent");
  await page.getByLabel("Manifest").fill(JSON.stringify({
    name: "support-agent",
    runtime: {
      framework: "langgraph",
      adapter: "langgraph",
      entrypoint: "agent:create_agent",
    },
    dependencies: [
      { name: "langgraph", version: "1.2.1" },
      { name: "custom-toolkit" },
    ],
    capabilities: { invoke: true },
  }, null, 2));
  await page.getByRole("button", { name: "Validate package" }).click();

  await expect(page.locator("dd", { hasText: /^valid$/ })).toBeVisible();
  await expect(page.locator("dd", { hasText: /^pkgval_e2e$/ })).toBeVisible();
  await expect(page.locator("dd", { hasText: /^create_ready_agent_version$/ })).toBeVisible();
  await expect(page.getByText("Dependency custom-toolkit does not declare a version.")).toBeVisible();

  await page.getByRole("button", { name: "Create ready version" }).click();
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.getByText("Ready version source")).toBeVisible();
  await page.locator("form.nested-form input[placeholder='0.1.0']").fill("1.0.0");
  await page.getByRole("button", { name: "Create ready AgentVersion" }).click();

  const versionRow = page.locator("tr").filter({ hasText: "1.0.0" }).first();
  await expect(versionRow).toContainText("ready");
});

test("explains invalid package manifest and readiness gate", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/packages/register");

  await page.getByLabel("Adapter").selectOption("deepagents");
  await page.getByLabel("Entrypoint").fill("agent:create_agent");
  await page.getByLabel("Manifest").fill(JSON.stringify({
    runtime: {
      framework: "langgraph",
      adapter: "deepagents",
      entrypoint: "agent:create_other",
    },
  }, null, 2));
  await page.getByRole("button", { name: "Validate package" }).click();

  await expect(page.locator("dd", { hasText: /^invalid$/ })).toBeVisible();
  await expect(page.locator("strong", { hasText: /^unsupported_runtime_pair$/ })).toBeVisible();
  await expect(page.locator("strong", { hasText: /^manifest_runtime_mismatch$/ })).toBeVisible();
  await expect(page.getByText("Ready versions require a validation token.")).toBeVisible();
});

test("shows missing secret and unsupported capability validation results", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/packages/register");

  await page.getByLabel("Required secret refs").fill("vault://openai");
  await page.getByLabel("Manifest").fill(JSON.stringify({
    runtime: {
      framework: "langgraph",
      adapter: "langgraph",
      entrypoint: "agent:create_agent",
    },
    capabilities: { unsupported_magic: true },
  }, null, 2));
  await page.getByRole("button", { name: "Validate package" }).click();

  await expect(page.locator("dd", { hasText: /^invalid$/ })).toBeVisible();
  await expect(page.locator("strong", { hasText: /^required_secret_missing$/ })).toBeVisible();
  await expect(page.locator("strong", { hasText: /^unsupported_capability$/ })).toBeVisible();
  await expect(page.getByText(/^vault:\/\/openai$/)).toBeVisible();
});
