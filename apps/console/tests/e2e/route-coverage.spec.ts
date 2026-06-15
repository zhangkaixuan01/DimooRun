import { expect, test, type Page } from "@playwright/test";

import {
  installConsoleApiMocks,
  seedConsoleSession,
  seedEnglishLocale,
} from "../fixtures/api";

const nonRedirectRoutes = [
  "/login",
  "/dashboard",
  "/agents",
  "/packages/register",
  "/deployments",
  "/deployments/10",
  "/compatibility",
  "/published-surfaces",
  "/published-surfaces/1",
  "/runtime/workers",
  "/runtime/agent-instances",
  "/runtime/capacity",
  "/runtime/schedules",
  "/runtime/batches",
  "/runs",
  "/runs/1001",
  "/runs/1001/triage",
  "/tasks",
  "/events",
  "/replay",
  "/replay/compare",
  "/governance/human-tasks",
  "/governance/policies",
  "/identity/operators",
  "/identity/operators/1",
  "/identity/scopes",
  "/identity/roles-permissions",
  "/identity/machine-identities",
  "/identity/service-accounts/1",
  "/governance/model-gateways",
  "/governance/tools",
  "/governance/secrets",
  "/governance/catalog-items",
  "/governance/catalog-items/1",
  "/governance/catalog-items/1/diff",
  "/governance/prompt-assets",
  "/governance/prompt-assets/1",
  "/governance/prompt-assets/1/diff",
  "/governance/config-assets",
  "/governance/config-assets/1",
  "/governance/config-assets/1/diff",
  "/governance/template-assets",
  "/governance/template-assets/1",
  "/governance/template-assets/1/diff",
  "/observability/audit-logs",
  "/observability/artifacts",
  "/observability/evaluations",
  "/observability/datasets",
  "/observability/experiments",
  "/observability/quality-gate",
  "/observability/costs",
  "/observability/budgets",
  "/observability/replay-jobs",
  "/observability/feedback",
  "/ops/recovery",
  "/ops/webhooks",
  "/ops/alerts",
  "/ops/incidents",
  "/settings/platform",
  "/settings/providers",
  "/settings/danger-zone",
  "/settings/semantic-store",
  "/settings/observability-exporters",
  "/settings/sandbox-policies",
  "/settings/container-pool-policies",
  "/settings",
] as const;

async function assertNoPageOverflow(page: Page, routePath: string) {
  const hasOverflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  expect(hasOverflow, `${routePath} should not create document-level horizontal overflow`).toBe(false);
}

test("all non-redirect routes render inside the operator shell without page overflow", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 1024, height: 768 });

  for (const routePath of nonRedirectRoutes) {
    await page.goto(routePath);
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByText(/DimooRun|Runtime Control Plane|Sign in/i).first()).toBeVisible();
    await assertNoPageOverflow(page, routePath);
  }
});

test("operator workbench typography stays restrained", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");

  const pageTitleSize = await page.locator(".page-title").first().evaluate((node) => {
    return Number.parseFloat(window.getComputedStyle(node).fontSize);
  });
  expect(pageTitleSize).toBeLessThanOrEqual(24);

  const metricValueSizes = await page.locator(".metric-value").evaluateAll((nodes) => {
    return nodes.map((node) => Number.parseFloat(window.getComputedStyle(node).fontSize));
  });
  expect(metricValueSizes.length).toBeGreaterThan(0);
  for (const size of metricValueSizes) {
    expect(size).toBeLessThanOrEqual(24);
  }
});

test("shell fits both supported locales without topbar overflow", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.setViewportSize({ width: 768, height: 720 });

  for (const locale of ["zh-CN", "en-US"] as const) {
    await page.goto("/dashboard");
    await page.evaluate((nextLocale) => {
      localStorage.setItem("dimoorun.console.locale", nextLocale);
    }, locale);
    await page.reload();
    await expect(page.locator(".topbar")).toBeVisible();
    await assertNoPageOverflow(page, `/dashboard:${locale}`);
  }
});

test("shell search and refresh controls are operational", async ({ page }) => {
  await seedEnglishLocale(page);
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.goto("/dashboard");

  await page.getByLabel("Global search").fill("deployments");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/deployments$/);

  await page.getByLabel("Global search").fill("missing workflow");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toHaveText("No matching page");

  await page.getByRole("button", { name: "Pause refresh" }).click();
  await expect(page.getByRole("button", { name: "Resume refresh" })).toBeVisible();
  await page.getByRole("button", { name: "Resume refresh" }).click();
  await expect(page.getByRole("button", { name: "Pause refresh" })).toBeVisible();
});

test("form controls use regular text weight in dense workflow forms", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.goto("/agents");

  await page.getByRole("button", { name: /Register Agent|注册智能体/ }).click();
  const controls = await page.locator("input, textarea, select").evaluateAll((nodes) =>
    nodes.map((node) => ({
      tag: node.tagName.toLowerCase(),
      className: (node as HTMLElement).className,
      value: (node as HTMLInputElement).value,
      weight: Number.parseInt(window.getComputedStyle(node).fontWeight, 10),
    })),
  );

  expect(controls.length).toBeGreaterThan(0);
  expect(controls.filter((control) => control.weight > 500)).toEqual([]);
});

test("representative workflow pages avoid visible English UI copy in Chinese locale", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);
  await page.goto("/dashboard");
  await page.evaluate(() => {
    localStorage.setItem("dimoorun.console.locale", "zh-CN");
  });

  const checks = [
    { path: "/governance/catalog-items", blocked: /Inventory|Create asset|Status summary|Audit reason/i },
    { path: "/compatibility", blocked: /Migration report|Create assistant|Runtime explorer|Generate migration report/i },
    { path: "/runtime/schedules", blocked: /Schedule preview|Schedules|Manual controls|Audit reason/i },
    { path: "/runtime/batches", blocked: /Batch create|Batch inventory|Failed item drilldown|Audit reason/i },
    { path: "/settings", blocked: /Preferences|Platform workflows|Control surfaces|Danger Zone/i },
  ] as const;

  for (const check of checks) {
    await page.goto(check.path);
    await expect(page.locator("body")).not.toContainText(check.blocked);
    await assertNoPageOverflow(page, check.path);
  }
});
