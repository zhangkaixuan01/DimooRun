import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("shows integration proof across run detail, adapter certification, and package trust", async ({ page }) => {
  await seedConsoleSession(page);
  await page.addInitScript(() => localStorage.setItem("dimoorun.console.locale", "en-US"));
  await installConsoleApiMocks(page);

  await page.goto("/runs/1001");
  const integrationPanel = page.locator("#integration-evidence");
  await expect(integrationPanel.getByRole("heading", { name: "Integration evidence" })).toBeVisible();
  await expect(integrationPanel.getByRole("link", { name: "Langfuse trace" })).toHaveAttribute(
    "href",
    "https://langfuse.example.test/project/support/traces/trace-1001",
  );
  await expect(integrationPanel.getByText("trace-1001")).toBeVisible();
  await expect(integrationPanel.getByText("opentelemetry").first()).toBeVisible();
  await expect(integrationPanel.getByText("delivered", { exact: true })).toBeVisible();
  await expect(integrationPanel.getByText("litellm", { exact: true })).toBeVisible();
  await expect(integrationPanel.getByText("gpt-4.1-mini")).toBeVisible();
  await expect(integrationPanel.getByText("otlp_retry")).toBeVisible();

  await page.goto("/compatibility");
  const matrix = page.getByRole("region", { name: "Adapter certification matrix" });
  await expect(matrix.getByRole("columnheader", { name: "invoke" })).toBeVisible();
  await expect(matrix.getByRole("columnheader", { name: "error mapping" })).toBeVisible();
  await expect(matrix.getByRole("row", { name: /LangGraph/ }).getByText("certified").first()).toBeVisible();
  await expect(matrix.getByRole("row", { name: /LangChain Agent/ }).getByText("unsupported")).toBeVisible();
  await expect(matrix.getByRole("row", { name: /DeepAgents/ }).getByText("not exercised")).toBeVisible();

  await page.goto("/agents");
  await page.getByRole("button", { name: "Open trust evidence" }).first().click();
  const trustDialog = page.getByRole("dialog", { name: "Package trust evidence" });
  await expect(trustDialog.getByText("tok_support_100", { exact: true })).toBeVisible();
  await expect(trustDialog.getByRole("link", { name: "Adapter certification matrix" })).toHaveAttribute(
    "href",
    "/compatibility?adapter=langgraph&framework=langgraph",
  );
  await expect(trustDialog.getByRole("link", { name: "Run evidence" })).toHaveAttribute(
    "href",
    "/runs?agent_version_id=11",
  );
});
