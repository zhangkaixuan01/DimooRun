import { execFileSync } from "node:child_process";
import http from "node:http";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium, expect } from "@playwright/test";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const distDir = path.join(rootDir, "dist");
const indexPath = path.join(distDir, "index.html");
const reportDir = path.resolve(rootDir, process.env.PLAYWRIGHT_HTML_REPORT || "playwright-report-0o");
const phaseProofPath = path.join(rootDir, ".phase-e2e-proof.json");
const localEnvFile = ".env.e2e.local";
const chromeEnvName = "DIMOORUN_PLAYWRIGHT_CHROME";
const serverHost = "127.0.0.1";
const preferredServerPort = 4173;
const args = process.argv.slice(2);
const outputIndex = args.findIndex((value) => value === "--output");
const outputDir = outputIndex >= 0 ? path.resolve(rootDir, args[outputIndex + 1]) : path.resolve(rootDir, "test-results-0o");

function readLocalEnv(name) {
  const envPath = path.join(rootDir, localEnvFile);
  if (!existsSync(envPath)) return undefined;
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;
    const key = trimmed.slice(0, separator).trim();
    if (key !== name) continue;
    return trimmed.slice(separator + 1).trim().replace(/^["']|["']$/g, "");
  }
  return undefined;
}

function ensureCleanDir(targetPath) {
  try {
    rmSync(targetPath, { force: true, recursive: true });
  } catch (error) {
    console.warn(`Failed to clean ${targetPath}:`, error);
  }
  mkdirSync(targetPath, { recursive: true });
}

function contentType(ext) {
  switch (ext) {
    case ".css":
      return "text/css; charset=utf-8";
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "application/javascript; charset=utf-8";
    case ".json":
      return "application/json; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    case ".txt":
      return "text/plain; charset=utf-8";
    case ".woff":
      return "font/woff";
    case ".woff2":
      return "font/woff2";
    default:
      return "application/octet-stream";
  }
}

function createGovernedAssets(createdAt) {
  return [
    {
      id: 810,
      kind: "prompt",
      name: "support-prompt",
      version: "1.0.0",
      status: "published",
      content_ref: "inline:triage-v1",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 811,
      kind: "prompt",
      name: "support-prompt",
      version: "1.1.0",
      status: "draft",
      content_ref: "inline:triage-v2",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "pending", validated_at: null, issues: [] },
      _dependencies: [{ kind: "template", name: "support-template", version: "2.0.0" }],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 812,
      kind: "prompt",
      name: "live-prompt",
      version: "1.0.0",
      status: "published",
      content_ref: "inline:live",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [{ resource_kind: "deployment", resource_id: 10, environment: "production", status: "active", active: true }],
      _risk_flags: ["active_deployment_dependency"],
    },
    {
      id: 813,
      kind: "prompt",
      name: "broken-prompt",
      version: "latest",
      status: "draft",
      content_ref: "inline:broken",
      visibility_level: "internal",
      created_at: createdAt,
      updated_at: createdAt,
      _validation: {
        status: "failed",
        validated_at: createdAt,
        issues: [
          { code: "explicit_version_required", field: "version", message: "latest is not allowed." },
          { code: "secret_ref_invalid", field: "secret_refs", message: "Invalid secret ref: bad-secret-ref" },
        ],
      },
      _dependencies: [{ kind: "prompt", name: "missing", version: "latest" }],
      _used_by: [],
      _risk_flags: ["floating_version"],
    },
    {
      id: 820,
      kind: "catalog",
      name: "runtime-tool",
      version: "1.0.0",
      status: "published",
      type: "tool",
      provider: "local",
      risk_level: "high",
      schema: {},
      capabilities: { invoke: true },
      runtime_requirements: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "prompt", name: "support-prompt", version: "1.0.0" }],
      _used_by: [{ resource_kind: "agent_version", resource_id: 12, environment: null, status: "ready", active: true }],
      _risk_flags: ["high_risk_component"],
    },
    {
      id: 821,
      kind: "catalog",
      name: "crm-mcp",
      version: "1.0.0",
      status: "published",
      type: "mcp_endpoint",
      provider: "remote",
      risk_level: "medium",
      schema: {},
      capabilities: { invoke: true },
      runtime_requirements: { model_gateway_refs: ["default-gateway"] },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "prompt", name: "support-prompt", version: "1.0.0" }],
      _used_by: [{ resource_kind: "agent_version", resource_id: 11, environment: null, status: "ready", active: true }],
      _risk_flags: [],
    },
    {
      id: 822,
      kind: "catalog",
      name: "shared-vector-memory",
      version: "1.0.0",
      status: "approved",
      type: "semantic_store",
      provider: "chroma",
      risk_level: "medium",
      schema: {},
      capabilities: { search: true },
      runtime_requirements: { retrieval_mode: "hybrid" },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "config", name: "production-config", version: "1.0.0" }],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 823,
      kind: "catalog",
      name: "governed-sandbox",
      version: "1.0.0",
      status: "published",
      type: "runtime_component",
      provider: "native",
      risk_level: "critical",
      schema: {},
      capabilities: { sandbox: true },
      runtime_requirements: { isolation_level: "process" },
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [{ kind: "template", name: "support-template", version: "2.0.0" }],
      _used_by: [{ resource_kind: "deployment", resource_id: 10, environment: "production", status: "active", active: true }],
      _risk_flags: ["high_risk_component", "active_deployment_dependency"],
    },
    {
      id: 830,
      kind: "config",
      name: "production-config",
      version: "1.0.0",
      status: "approved",
      content_ref: "inline:cfg",
      environment: "production",
      schema: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
    {
      id: 840,
      kind: "template",
      name: "support-template",
      version: "2.0.0",
      status: "published",
      type: "template",
      content_ref: "inline:template",
      schema: {},
      created_at: createdAt,
      updated_at: createdAt,
      _validation: { status: "passed", validated_at: createdAt, issues: [] },
      _dependencies: [],
      _used_by: [],
      _risk_flags: [],
    },
  ];
}

function listGovernedAssets(assets, kind) {
  return assets
    .filter((item) => item.kind === kind)
    .map((item) => ({
      id: item.id,
      name: item.name,
      version: item.version,
      status: item.status,
      type: item.type,
      provider: item.provider,
      risk_level: item.risk_level,
      visibility_level: item.visibility_level,
      environment: item.environment ?? null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    }));
}

function governedAssetDetailResponse(assets, item) {
  const history = assets
    .filter((entry) => entry.kind === item.kind && entry.name === item.name && entry.type === item.type)
    .sort((left, right) => left.id - right.id);
  const previousIndex = history.findIndex((entry) => entry.id === item.id) - 1;
  const previous = previousIndex >= 0 ? history[previousIndex] : null;
  const changedFields = previous
    ? [
      { field: "content_ref", before: previous.content_ref ?? null, after: item.content_ref ?? null },
      { field: "version", before: previous.version, after: item.version },
    ].filter((entry) => entry.before !== entry.after)
    : [];
  return {
    item: {
      id: item.id,
      name: item.name,
      version: item.version,
      status: item.status,
      kind: item.kind,
      type: item.type,
      provider: item.provider,
      risk_level: item.risk_level,
      visibility_level: item.visibility_level,
      environment: item.environment ?? null,
      content_ref: item.content_ref,
      schema: item.schema ?? {},
      capabilities: item.capabilities ?? {},
      runtime_requirements: item.runtime_requirements ?? {},
      created_at: item.created_at,
      updated_at: item.updated_at,
    },
    lifecycle: { status: item.status, last_action: item.status },
    validation: item._validation || { status: "pending", issues: [] },
    dependencies: item._dependencies || [],
    used_by: item._used_by || [],
    risk_flags: item._risk_flags || [],
    version_history: history.map((entry) => ({
      id: entry.id,
      name: entry.name,
      version: entry.version,
      status: entry.status,
    })),
    diff_to_previous: { changed_fields: changedFields, has_changes: changedFields.length > 0 },
    environment: item.environment ?? null,
  };
}

function jsonResponse(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    json: payload,
  });
}

function errorResponse(route, errorCode, message, status = 400) {
  return route.fulfill({
    status,
    contentType: "application/json",
    json: {
      detail: {
        error_code: errorCode,
        message,
        request_id: "browser-proof-error",
      },
    },
  });
}

function nextNumericId(items) {
  return Math.max(...items.map((item) => Number(item.id || 0))) + 1;
}

function parseBody(route) {
  const body = route.request().postData();
  if (!body) return {};
  const parsed = JSON.parse(body);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
}

async function installMockApi(page, assets, baseUrl) {
  await page.route(`${baseUrl}/mock-api/**`, async (route) => {
    const url = new URL(route.request().url());
    const pathName = url.pathname.replace("/mock-api", "");
    const method = route.request().method();

    if (pathName === "/v1/assets/prompts" && method === "GET") {
      return jsonResponse(route, { items: listGovernedAssets(assets, "prompt"), count: 4, request_id: "browser-proof" });
    }
    if (pathName === "/v1/assets/prompts" && method === "POST") {
      const body = parseBody(route);
      const createdAt = "2026-06-05T00:00:00.000Z";
      const created = {
        id: nextNumericId(assets),
        kind: "prompt",
        name: String(body.name || `prompt-${assets.length + 1}`),
        version: String(body.version || "1.0.0"),
        status: "draft",
        content_ref: String(body.content_ref || "inline:content"),
        visibility_level: "internal",
        created_at: createdAt,
        updated_at: createdAt,
        _validation: { status: "pending", validated_at: null, issues: [] },
        _dependencies: [],
        _used_by: [],
        _risk_flags: [],
      };
      assets.unshift(created);
      return jsonResponse(route, { item: listGovernedAssets([created], "prompt")[0], request_id: "browser-proof" });
    }
    if (pathName === "/v1/catalog/items" && method === "GET") {
      return jsonResponse(route, { items: listGovernedAssets(assets, "catalog"), count: 4, request_id: "browser-proof" });
    }

    const detailMatch = pathName.match(/^\/v1\/(catalog\/items|assets\/prompts)\/(\d+)$/);
    if (detailMatch && method === "GET") {
      const kind = detailMatch[1] === "catalog/items" ? "catalog" : "prompt";
      const item = assets.find((entry) => entry.kind === kind && entry.id === Number(detailMatch[2]));
      if (!item) return errorResponse(route, `${kind}_asset_not_found`, "Asset not found.", 404);
      return jsonResponse(route, governedAssetDetailResponse(assets, item));
    }

    const actionMatch = pathName.match(/^\/v1\/(catalog\/items|assets\/prompts)\/(\d+)\/(validate|approve|publish|deprecate|archive|rollback)$/);
    if (actionMatch && method === "POST") {
      const kind = actionMatch[1] === "catalog/items" ? "catalog" : "prompt";
      const item = assets.find((entry) => entry.kind === kind && entry.id === Number(actionMatch[2]));
      const action = actionMatch[3];
      const body = parseBody(route);
      if (!item) return errorResponse(route, `${kind}_asset_not_found`, "Asset not found.", 404);
      if (action === "validate") {
        if (item.name === "broken-prompt") {
          return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status }, validation: item._validation });
        }
        item.status = "validated";
        item._validation = { status: "passed", validated_at: "2026-06-05T00:00:00.000Z", issues: [] };
        return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status }, validation: item._validation });
      }
      if (action === "approve") {
        item.status = "approved";
        return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status } });
      }
      if (action === "publish") {
        for (const sibling of assets) {
          if (sibling.kind === item.kind && sibling.name === item.name && sibling.id !== item.id && sibling.status === "published") {
            sibling.status = "deprecated";
          }
        }
        item.status = "published";
        return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status } });
      }
      if (action === "deprecate" && (item._used_by || []).some((entry) => entry.active === true)) {
        return errorResponse(route, "asset_in_use_by_active_deployment", "Asset is still referenced by an active deployment.", 409);
      }
      if (action === "deprecate") {
        item.status = "deprecated";
        return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status }, used_by: item._used_by || [] });
      }
      if (action === "archive") {
        item.status = "archived";
        return jsonResponse(route, { item: { id: item.id, name: item.name, version: item.version, status: item.status }, lifecycle: { status: item.status } });
      }
      const targetVersion = String(body.target_version || "");
      const target = assets.find((entry) => entry.kind === kind && entry.name === item.name && entry.version === targetVersion);
      if (!target) return errorResponse(route, "rollback_target_not_found", "Rollback target version was not found.", 404);
      item.status = "deprecated";
      target.status = "published";
      return jsonResponse(route, {
        item: { id: target.id, name: target.name, version: target.version, status: target.status },
        rolled_back_from: { id: item.id, name: item.name, version: item.version, status: item.status },
        lifecycle: { status: target.status },
      });
    }

    return errorResponse(route, "unsupported_mock_path", `Unsupported mock path: ${method} ${pathName}`, 404);
  });
}

function escapePowerShell(value) {
  return String(value).replace(/'/g, "''");
}

async function waitForCdp(port) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return;
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for CDP on port ${port}.`);
}

async function launchBrowserWithFallback(configuredChrome) {
  const launchOptions = configuredChrome ? { executablePath: configuredChrome } : undefined;
  try {
    const browser = await chromium.launch(launchOptions);
    return {
      browser,
      createContext: async () => browser.newContext(),
      cleanup: async () => {
        await browser.close();
      },
    };
  } catch (error) {
    if (!(error instanceof Error) || !String(error.message).includes("spawn EPERM")) {
      throw error;
    }
  }

  const executablePath = configuredChrome || chromium.executablePath();
  const cdpPort = 9223;
  const userDataDir = path.join(os.tmpdir(), `dimoorun-cdp-${Date.now()}`);
  mkdirSync(userDataDir, { recursive: true });
  const browserArgs = [
    "--remote-debugging-port=9223",
    `--user-data-dir=${userDataDir}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-extensions",
    "--disable-popup-blocking",
    "--mute-audio",
    "--no-sandbox",
    "--hide-scrollbars",
    "--disable-features=Translate,MediaRouter",
    "--disable-search-engine-choice-screen",
    "--remote-allow-origins=*",
    "about:blank",
  ];
  const argumentList = browserArgs.map((entry) => `'${escapePowerShell(entry)}'`).join(", ");
  const command = [
    `$p = Start-Process -FilePath '${escapePowerShell(executablePath)}'`,
    `-ArgumentList ${argumentList}`,
    "-WindowStyle Hidden -PassThru;",
    "$p.Id",
  ].join(" ");
  const pidText = execFileSync(
    "powershell",
    ["-NoProfile", "-Command", command],
    { encoding: "utf8" },
  ).trim();
  const pid = Number(pidText);
  await waitForCdp(cdpPort);
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`);
  return {
    browser,
    createContext: async () => {
      const existing = browser.contexts()[0];
      if (existing) return existing;
      throw new Error("CDP browser did not expose a reusable context.");
    },
    cleanup: async () => {
      await browser.close();
      try {
        execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
      } catch {
        // best-effort cleanup
      }
      try {
        rmSync(userDataDir, { force: true, recursive: true });
      } catch {
        // ignore
      }
    },
  };
}

async function startServer() {
  if (!existsSync(indexPath)) {
    throw new Error("Missing dist/index.html. Run `npm run build:e2e` first.");
  }
  const server = http.createServer((request, response) => {
    const requestUrl = new URL(request.url || "/", `http://${serverHost}:${preferredServerPort}`);
    let filePath = path.join(
      distDir,
      requestUrl.pathname === "/" ? "index.html" : decodeURIComponent(requestUrl.pathname.slice(1)),
    );
    if (!filePath.startsWith(distDir)) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }
    if (!existsSync(filePath)) {
      filePath = indexPath;
    }
    const body = readFileSync(filePath);
    response.writeHead(200, {
      "Content-Type": contentType(path.extname(filePath)),
      "Cache-Control": "no-cache",
    });
    response.end(body);
  });
  const listenOnPort = (port) =>
    new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, serverHost, () => {
        server.off("error", reject);
        resolve();
      });
    });
  try {
    await listenOnPort(preferredServerPort);
  } catch (error) {
    if (!(error instanceof Error) || !String(error.message).includes("EADDRINUSE")) {
      throw error;
    }
    await listenOnPort(0);
  }
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("Failed to resolve local browser proof server address.");
  }
  return {
    server,
    baseUrl: `http://${serverHost}:${address.port}`,
  };
}

async function stopServer(server) {
  await new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
}

async function screenshot(page, name) {
  const target = path.join(outputDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: true });
  return path.basename(target);
}

function writeHtmlReport(steps) {
  const items = steps
    .map((step) => `<li><strong>${step.name}</strong>${step.screenshot ? ` <a href="../${step.screenshot}">screenshot</a>` : ""}</li>`)
    .join("");
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Phase 0O Browser Proof</title></head><body><h1>Phase 0O Browser Proof</h1><p>Manual browser proof succeeded without Playwright worker processes.</p><ol>${items}</ol></body></html>`;
  mkdirSync(reportDir, { recursive: true });
  writeFileSync(path.join(reportDir, "index.html"), html, "utf8");
}

function writePhaseProof() {
  writeFileSync(
    phaseProofPath,
    JSON.stringify(
      {
        spec_path: "tests/e2e/catalog-assets.spec.ts",
        output_dir: path.relative(rootDir, outputDir).replace(/\\/g, "/"),
        html_report_dir: path.relative(rootDir, reportDir).replace(/\\/g, "/"),
        phases: ["0o"],
        generated_at: new Date().toISOString(),
        proof_mode: "manual-browser",
      },
      null,
      2,
    ),
    "utf8",
  );
}

async function main() {
  ensureCleanDir(outputDir);
  ensureCleanDir(reportDir);

  const configuredChrome = process.env[chromeEnvName] || readLocalEnv(chromeEnvName);
  const runtime = await launchBrowserWithFallback(configuredChrome);
  const { server, baseUrl } = await startServer();
  const context = await runtime.createContext();
  const page = await context.newPage();
  const createdAt = "2026-06-05T00:00:00.000Z";
  const assets = createGovernedAssets(createdAt);
  const steps = [];

  try {
    await installMockApi(page, assets, baseUrl);
    await page.addInitScript(() => {
      localStorage.setItem("dimoorun.console.locale", "en-US");
      localStorage.setItem("dimoorun.console.token", "sess_e2e_session");
      localStorage.setItem("dimoorun.console.operator", JSON.stringify({
        id: 1,
        email: "admin@local.dimoorun",
        name: "E2E Operator",
        roles: ["platform_admin"],
        permissions: ["*"],
        allowed_scopes: [{
          tenant_id: 1,
          tenant_name: "Local Tenant",
          project_id: 1,
          project_name: "DimooRun",
          environment: "local",
          environment_name: "Local",
        }],
        status: "active",
        created_at: "2026-01-01T00:00:00.000Z",
        updated_at: "2026-01-01T00:00:00.000Z",
        last_login_at: null,
        password_changed_at: null,
      }));
      localStorage.setItem("dimoorun.console.scope", JSON.stringify({
        tenant_id: 1,
        tenant_name: "Local Tenant",
        project_id: 1,
        project_name: "DimooRun",
        environment: "local",
        environment_name: "Local",
      }));
      sessionStorage.setItem("dimoorun.console.apiBaseUrlOverride", `${window.location.origin}/mock-api`);
    });

    await page.goto(`${baseUrl}/governance/prompt-assets`);
    await expect(page.getByRole("heading", { name: "Prompt Assets", exact: true })).toBeVisible();
    await page.getByLabel("Name").fill("billing-prompt");
    await page.getByLabel("Version").fill("2.0.0");
    await page.getByLabel("Content ref").fill("inline:billing");
    await page.getByRole("button", { name: "Create asset" }).click();
    await expect(page.getByText("Created asset #")).toBeVisible();
    steps.push({ name: "create prompt asset", screenshot: await screenshot(page, "01-create-prompt") });

    await page.goto(`${baseUrl}/governance/prompt-assets/813`);
    await expect(page.getByRole("heading", { name: "broken-prompt", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page.getByText("explicit_version_required")).toBeVisible();
    await expect(page.getByText("secret_ref_invalid")).toBeVisible();
    steps.push({ name: "show validation failure", screenshot: await screenshot(page, "02-validation-failure") });

    await page.goto(`${baseUrl}/governance/prompt-assets/811/diff`);
    await expect(page.getByRole("heading", { name: "Version diff", exact: true })).toBeVisible();
    await expect(page.getByText("content_ref")).toBeVisible();
    await expect(page.getByText("inline:triage-v1")).toBeVisible();
    await expect(page.getByText("inline:triage-v2")).toBeVisible();
    steps.push({ name: "render prompt diff", screenshot: await screenshot(page, "03-prompt-diff") });

    await page.goto(`${baseUrl}/governance/prompt-assets/811`);
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page.getByText("validation passed")).toBeVisible();
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approve -> approved")).toBeVisible();
    await page.getByRole("button", { name: "Publish" }).click();
    await expect(page.getByText("publish -> published")).toBeVisible();

    await page.goto(`${baseUrl}/governance/prompt-assets/812`);
    await page.getByRole("button", { name: "Deprecate" }).click();
    await expect(page.getByText("Asset is still referenced by an active deployment.")).toBeVisible();

    await page.goto(`${baseUrl}/governance/prompt-assets/811`);
    await page.getByLabel("Rollback target").selectOption("1.0.0");
    await page.getByRole("button", { name: "Rollback" }).click();
    await expect(page).toHaveURL(/\/governance\/prompt-assets\/810$/);
    await expect(page.getByText("v1.0.0 · published", { exact: true })).toBeVisible();
    steps.push({ name: "complete lifecycle actions", screenshot: await screenshot(page, "04-lifecycle-actions") });

    await page.goto(`${baseUrl}/governance/catalog-items`);
    await expect(page.getByRole("heading", { name: "Catalog Items", exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "mcp_endpoint" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "semantic_store" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "runtime_component" })).toBeVisible();
    const runtimeComponentRow = page.getByRole("row", { name: /governed-sandbox/ });
    await runtimeComponentRow.getByRole("link", { name: "Open" }).click();
    await expect(page.getByRole("heading", { name: "governed-sandbox", exact: true })).toBeVisible();
    await expect(page.getByText("Asset facts")).toBeVisible();
    await expect(page.getByText("Shape · runtime_component")).toBeVisible();
    await expect(page.getByText("Provider · native")).toBeVisible();
    await expect(page.getByText("Runtime requirements")).toBeVisible();
    await expect(page.getByText("isolation_level · process")).toBeVisible();
    await expect(page.getByText("active_deployment_dependency")).toBeVisible();
    steps.push({ name: "prove catalog item shapes", screenshot: await screenshot(page, "05-catalog-shapes") });

    writeHtmlReport(steps);
    writePhaseProof();
    console.log("Catalog assets browser proof completed.");
  } finally {
    await context.close();
    await runtime.cleanup();
    await stopServer(server);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
