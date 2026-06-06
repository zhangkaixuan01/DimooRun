import { expect, test } from "@playwright/test";

import { installConsoleApiMocks, seedConsoleSession } from "../fixtures/api";

test("renders dashboard workflow data from mocked API responses", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page);

  await page.goto("/dashboard");

  await expect(page.getByRole("heading", { name: "仪表盘" })).toBeVisible();
  await expect(page.getByText("3", { exact: true })).toBeVisible();
  await expect(page.getByText("50.0%")).toBeVisible();
  await expect(page.getByText("1 / 2 ready")).toBeVisible();
  await expect(page.getByRole("link", { name: "101" })).toBeVisible();
  await expect(page.getByText("deployment.promote")).toBeVisible();
  await expect(page.getByText("Deployment must be active before it can restart.")).toBeVisible();
  await expect(page.getByText("provider outage").first()).toBeVisible();
});

test("renders empty API state with scoped mocked responses", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { empty: true });

  await page.goto("/agents");

  await expect(page.getByRole("heading", { name: "智能体" })).toBeVisible();
  await expect(page.getByText("暂无数据")).toBeVisible();
  await expect(page.getByText("后端返回空集合，可用创建操作生成第一条记录。")).toBeVisible();
});

test("renders slow loading state before mocked API data arrives", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { delayPath: "/v1/agents" });

  await page.goto("/agents");

  await expect(page.getByText("加载中")).toBeVisible();
  await expect(page.getByRole("table").first()).toBeVisible();
});

test("renders normalized API errors without losing page context", async ({ page }) => {
  await seedConsoleSession(page);
  await installConsoleApiMocks(page, { errorPath: "/v1/agents" });

  await page.goto("/agents");

  await expect(page.getByRole("heading", { name: "智能体" })).toBeVisible();
  await expect(page.getByText("e2e_api_error")).toBeVisible();
  await expect(page.getByText("Mocked API failure.")).toBeVisible();
  await expect(page.getByText("request_id=e2e-error-request")).toBeVisible();
});
