import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession, seedEnglishLocale } from "../fixtures/api";

const expectedNavigation = {
  Overview: ["Dashboard"],
  Runtime: [
    "Agents",
    "Packages",
    "Deployments",
    "Published Surfaces",
    "Workers",
    "Agent instances",
    "Capacity",
    "Scheduled Runs",
    "Batch Runs",
    "Runs",
    "Tasks",
  ],
  Observability: [
    "Events",
    "Debug / Replay",
    "Audit Logs",
    "Artifacts",
    "Datasets",
    "Experiments",
    "Quality Gate",
    "Cost",
    "Budget",
    "Evaluation Results",
    "Feedback",
    "Replay Jobs",
  ],
  Identity: ["Organization Scope", "Operators", "Roles and permissions", "Machine identity"],
  Governance: [
    "Human Tasks",
    "Policies",
    "Model Gateways",
    "Tool Gateway",
    "Secrets",
    "Catalog Items",
    "Prompt Assets",
    "Config Assets",
    "Template Assets",
  ],
  "Enterprise Ops": ["Backup And Restore", "Webhook Subscriptions", "Alert Rules", "Incidents"],
  Compatibility: ["Compatibility"],
  Platform: [
    "Platform Settings",
    "Provider Status",
    "Danger Zone",
    "Semantic Store",
    "Observability Exporters",
    "Sandbox Policies",
    "Container Pool Policies",
    "Settings",
  ],
} as const;

test("console navigation exposes the reviewed module and submenu matrix", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");

  const navigation = page.getByRole("navigation");
  for (const [moduleName, submenus] of Object.entries(expectedNavigation)) {
    await expect(navigation.getByText(moduleName, { exact: true })).toBeVisible();
    for (const submenu of submenus) {
      await expect(navigation.getByRole("link", { name: submenu, exact: true })).toBeVisible();
    }
  }
});

test("high value routes do not render the generic collection title", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  const routes = [
    "/observability/audit-logs",
    "/observability/artifacts",
    "/observability/evaluations",
    "/observability/feedback",
    "/observability/replay-jobs",
    "/ops/webhooks",
    "/ops/alerts",
    "/settings/semantic-store",
    "/settings/observability-exporters",
    "/settings/sandbox-policies",
    "/settings/container-pool-policies",
    "/governance/policies",
  ];

  for (const route of routes) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: "Admin Collection" })).toHaveCount(0);
  }
});
