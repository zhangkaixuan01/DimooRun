import { expect, test } from "@playwright/test";

import {
  forceOfflineMode,
  installConsoleApiMocks,
  seedConsoleSession,
  seedEnglishLocale,
} from "../fixtures/api";

test("logs in and redirects into the dashboard workflow", async ({ page }) => {
  await seedEnglishLocale(page);
  await installConsoleApiMocks(page);

  await page.goto("/login?redirect=%2Fdashboard");

  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Password").fill("local-password");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(page.getByText("E2E Operator")).toBeVisible();
  await expect.poll(async () => page.evaluate(() => localStorage.getItem("dimoorun.console.token"))).toBe("sess_e2e_session");
});

test("covers the core runtime browser workflow from agent registration to replay and destructive confirmation", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/agents");

  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await page.getByRole("button", { name: "Register Agent" }).click();
  await expect(page.getByRole("dialog", { name: "Register Agent" })).toBeVisible();
  await page.getByLabel("Name").fill("ops-assistant");
  await page.getByLabel("Description").fill("Browser workflow proof agent");
  await page.getByRole("dialog", { name: "Register Agent" }).getByRole("button", { name: "Register Agent" }).click();

  await expect(page.getByRole("heading", { name: "ops-assistant" })).toBeVisible();
  await page.getByRole("button", { name: "Add version" }).first().click();
  await page.getByPlaceholder("0.1.0").fill("2.0.0");
  await page.getByPlaceholder("file:///opt/dimoorun/agents/support").fill("oci://registry.local/ops-assistant:2.0.0");
  await page.getByPlaceholder("agent:create_agent").fill("agent:create_agent");
  await page.getByRole("button", { name: "Create AgentVersion" }).click();

  await expect(page.getByRole("cell", { name: /2\.0\.0/ }).first()).toBeVisible();

  await page.goto("/deployments");

  await expect(page.getByRole("heading", { name: "Deployments" })).toBeVisible();
  await page.getByRole("button", { name: "Create Deployment" }).click();
  const createDeploymentDialog = page.getByRole("dialog", { name: "Create Deployment" });
  await expect(createDeploymentDialog).toBeVisible();
  await createDeploymentDialog.getByLabel("Agent").selectOption("2");
  await createDeploymentDialog.getByLabel("Version").selectOption("13");
  await createDeploymentDialog.getByLabel("Environment").fill("production");
  await createDeploymentDialog.getByLabel("Replicas").fill("2");
  await createDeploymentDialog.getByRole("button", { name: "Create Deployment" }).click();

  await expect(page.getByRole("heading", { name: /Deployment #/ })).toBeVisible();
  await page.getByRole("row").filter({ has: page.getByText(/^10$/) }).first().click();
  await page.getByRole("tab", { name: "Submit via Deployment" }).click();
  await page.getByLabel("thread_id").fill("thread-runtime-browser-proof");
  await page.getByRole("button", { name: "Submit via Deployment" }).click();

  await expect(page.getByText("Task created:")).toBeVisible();
  await page.getByRole("link", { name: /Run #/ }).click();

  await expect(page).toHaveURL(/\/runs\/\d+$/);
  await expect(page.getByText("Event Timeline")).toBeVisible();
  await expect(page.getByText("Input / Output / Error")).toBeVisible();
  await expect(page.getByText("Run attempts")).toBeVisible();

  await page.goto("/runs/1001/triage");

  await expect(page.getByRole("heading", { name: "Run triage #1001" })).toBeVisible();
  await page.getByRole("link", { name: "Compare replay" }).click();
  await expect(page.getByRole("heading", { name: "Replay comparison" })).toBeVisible();
  await page.getByLabel("Candidate version").selectOption("12");
  await page.getByLabel("Replay config").fill('{"temperature":0,"dataset_label":"phase6-browser-proof"}');
  await page.getByRole("button", { name: "Create comparison" }).click();

  await expect(page.getByText("Comparison #cmp-1001-12")).toBeVisible();
  await expect(page.getByText("Replay run #2001")).toBeVisible();

  await page.goto("/agents");
  await page.getByRole("button", { name: "Delete" }).first().click();

  const deleteAgentDialog = page.getByRole("alertdialog", { name: "Delete Agent" });
  await expect(deleteAgentDialog).toBeVisible();
  await expect(page.getByText("Historical runs, versions, and audit records are not physically deleted.")).toBeVisible();
  await deleteAgentDialog.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("heading", { name: "ops-assistant" })).not.toBeVisible();
});

test("shows the offline state when no API base URL is configured", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await forceOfflineMode(page);

  await page.goto("/agents");

  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.getByText("Live API is not configured")).toBeVisible();
  await expect(page.getByText("Set VITE_DIMOORUN_API_BASE_URL to connect the backend.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Register Agent" })).toBeDisabled();
});

test("renders the empty state for an empty runtime collection", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { empty: true });
  await page.goto("/agents");

  await expect(page.getByText("No data")).toBeVisible();
  await expect(page.getByText("The backend returned an empty collection.")).toBeVisible();
});

test("renders the loading state before runtime data arrives", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { delayPath: "/v1/agents" });
  await page.goto("/agents");

  await expect(page.getByText("Loading")).toBeVisible();
  await expect(page.getByRole("table").first()).toBeVisible();
});

test("renders normalized API errors without losing workflow context", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { errorPath: "/v1/agents" });
  await page.goto("/agents");

  await expect(page.getByText("e2e_api_error")).toBeVisible();
  await expect(page.getByText("Mocked API failure.")).toBeVisible();
  await expect(page.getByText("request_id=e2e-error-request")).toBeVisible();
});
