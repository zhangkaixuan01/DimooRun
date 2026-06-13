import { spawn } from "node:child_process";
import {
  appendFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createServer as createHttpServer } from "node:http";
import { createServer } from "node:net";
import { extname, join, normalize, resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { runDeploymentPromotionLiveSmoke } from "./deployment-promotion-live-smoke.mjs";
import { runEnterpriseOpsLiveSmoke } from "./enterprise-ops-live-smoke.mjs";
import { runGatewayGovernanceLiveSmoke } from "./gateway-governance-live-smoke.mjs";
import { runPackageVersionLiveSmoke } from "./package-version-live-smoke.mjs";
import { runPolicyApprovalLiveSmoke } from "./policy-approval-live-smoke.mjs";
import { runPublishedSurfaceLiveSmoke } from "./published-surface-live-smoke.mjs";
import { runQualityLoopLiveSmoke } from "./quality-loop-live-smoke.mjs";
import { runRunTriageLiveSmoke } from "./run-triage-live-smoke.mjs";

const consoleRoot = process.cwd();
const logDir = join(tmpdir(), "dimoorun-console-live-e2e");
mkdirSync(logDir, { recursive: true });
const logPath = join(logDir, "run-live-e2e.log");
writeFileSync(logPath, "");
const liveBackendPidFile = join(logDir, "live-backend-pids.json");
const liveGatewayFixtureFile = join(logDir, "live-gateway-fixture.json");
const nodeExecutable = process.execPath;
const backendHost = "127.0.0.1";
const backendPort = 4180;
const frontendHost = "127.0.0.1";
const frontendPort = 4174;
const distDir = resolve(consoleRoot, "dist");
const mockedApiBaseUrl = "http://127.0.0.1:4173/mock-api";
const liveApiBaseUrl = `http://${backendHost}:${backendPort}`;
const backendScript = resolve(consoleRoot, "scripts", "start-live-backend.mjs");
const childExitTimeoutMs = 3_000;
const taskkillTimeoutMs = 5_000;
const configuredHardTimeoutMs = Number(process.env.DIMOORUN_LIVE_E2E_TIMEOUT_MS);
const liveE2eHardTimeoutMs = Number.isInteger(configuredHardTimeoutMs) && configuredHardTimeoutMs > 0
  ? configuredHardTimeoutMs
  : 240_000;
const liveE2eEnv = {
  ...process.env,
  DIMOORUN_LIVE_API_BASE_URL: liveApiBaseUrl,
  DIMOORUN_LIVE_BACKEND_PID_FILE: liveBackendPidFile,
  DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE: liveGatewayFixtureFile,
  VITE_DIMOORUN_API_BASE_URL: liveApiBaseUrl,
  VITE_DIMOORUN_LOGIN_EMAIL: "admin@local.dimoorun",
};

const children = new Set();
const servers = new Set();
let hardTimeout = undefined;

function logStatus(message) {
  console.log(message);
  appendFileSync(logPath, `[${new Date().toISOString()}] ${message}\n`);
}

function track(child) {
  children.add(child);
  child.on("exit", () => {
    children.delete(child);
  });
  return child;
}

function assertPortAvailable(port, host) {
  return new Promise((resolvePort, rejectPort) => {
    const server = createServer();
    server.unref();
    server.once("error", (error) => {
      if (error && typeof error === "object" && "code" in error && error.code === "EADDRINUSE") {
        rejectPort(new Error(`Port ${port} is already in use on ${host}`));
        return;
      }
      rejectPort(error);
    });
    server.listen(port, host, () => {
      server.close((error) => {
        if (error) rejectPort(error);
        else resolvePort();
      });
    });
  });
}

function waitForChildExit(child, timeoutMs = childExitTimeoutMs) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();

  return new Promise((resolveExit, rejectExit) => {
    const timeout = setTimeout(() => {
      rejectExit(new Error(`Timed out waiting for child process to exit: ${child.pid ?? "unknown"}`));
    }, timeoutMs);
    const finish = () => {
      clearTimeout(timeout);
      resolveExit();
    };
    child.once("exit", finish);
    child.once("close", finish);
  });
}

function commandOutput(command, args) {
  return new Promise((resolveOutput) => {
    let child;
    try {
      child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"], shell: false });
    } catch (error) {
      logStatus(`Command output warning: ${error instanceof Error ? error.message : String(error)}`);
      resolveOutput("");
      return;
    }
    let stdout = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.on("exit", () => resolveOutput(stdout));
    child.on("error", () => resolveOutput(""));
  });
}

async function killChildTree(child) {
  if (child.killed) {
    await waitForChildExit(child);
    return;
  }

  if (process.platform !== "win32") {
    child.kill();
    await waitForChildExit(child);
    return;
  }

  if (!child.pid) {
    child.kill();
    await waitForChildExit(child);
    return;
  }

  await new Promise((resolveKill) => {
    const taskkill = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      shell: false,
    });
    const timeout = setTimeout(() => {
      logStatus(`Taskkill timed out for child process: ${child.pid}`);
      child.kill();
      resolveKill();
    }, taskkillTimeoutMs);
    const finish = () => {
      clearTimeout(timeout);
      resolveKill();
    };
    taskkill.on("exit", finish);
    taskkill.on("error", () => {
      clearTimeout(timeout);
      child.kill();
      resolveKill();
    });
  });
  await waitForChildExit(child);
}

async function killProcessId(pid) {
  try {
    process.kill(pid);
    return;
  } catch {
    // Fall back to taskkill below on Windows when Node cannot terminate the process.
  }

  await new Promise((resolveKill) => {
    const taskkill = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
      stdio: "ignore",
      shell: false,
    });
    taskkill.on("exit", () => resolveKill());
    taskkill.on("error", () => resolveKill());
  });
}

async function cleanupLiveBackendPidFile() {
  if (!existsSync(liveBackendPidFile)) return;

  try {
    const payload = JSON.parse(readFileSync(liveBackendPidFile, "utf8"));
    const pids = [payload.uvicorn_worker_pid, payload.server_pid, payload.launcher_pid]
      .map((pid) => Number(pid))
      .filter((pid) => Number.isInteger(pid) && pid > 0);
    const results = await Promise.allSettled(pids.map((pid) => killProcessId(pid)));
    for (const result of results) {
      if (result.status === "rejected") {
        logStatus(`Live backend PID cleanup warning: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`);
      }
    }
  } catch (error) {
    logStatus(`Live backend PID cleanup warning: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function cleanupPortListeners() {
  if (process.platform !== "win32") return;

  const output = await commandOutput("netstat", ["-ano"]);
  const ports = new Set([backendPort, frontendPort]);
  const pids = new Set();

  for (const line of output.split(/\r?\n/)) {
    const columns = line.trim().split(/\s+/);
    if (columns.length < 5 || columns[0] !== "TCP" || columns[3] !== "LISTENING") continue;

    const localAddress = columns[1] || "";
    const pid = Number(columns[4]);
    const port = Number(localAddress.slice(localAddress.lastIndexOf(":") + 1));
    if (ports.has(port) && Number.isInteger(pid) && pid > 0) {
      pids.add(pid);
    }
  }

  const results = await Promise.allSettled([...pids].map((pid) => killProcessId(pid)));
  for (const result of results) {
    if (result.status === "rejected") {
      logStatus(`Listening port cleanup warning: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`);
    }
  }
}

async function cleanup() {
  if (hardTimeout) {
    clearTimeout(hardTimeout);
    hardTimeout = undefined;
  }
  await cleanupLiveBackendPidFile();
  const results = await Promise.allSettled([...children].map((child) => killChildTree(child)));
  for (const result of results) {
    if (result.status === "rejected") {
      logStatus(`Cleanup warning: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`);
    }
  }
  await Promise.allSettled([...servers].map((server) => new Promise((resolveClose) => {
    server.close(() => resolveClose());
  })));
  await cleanupPortListeners();
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    void cleanup().finally(() => {
      process.exit(130);
    });
  });
}

function startManagedProcess(name, command, args, options = {}) {
  logStatus(`Starting ${name}: ${command} ${args.join(" ")}`);
  return track(spawn(command, args, {
    cwd: consoleRoot,
    shell: false,
    stdio: "inherit",
    ...options,
  }));
}

function run(command, args, options = {}, timeoutMs = 120_000) {
  return new Promise((resolveRun, rejectRun) => {
    const child = startManagedProcess("command", command, args, options);
    const timeout = setTimeout(() => {
      void killChildTree(child);
      rejectRun(new Error(`${command} ${args.join(" ")} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    child.on("exit", (code) => {
      clearTimeout(timeout);
      if (code === 0) resolveRun();
      else rejectRun(new Error(`${command} ${args.join(" ")} exited with ${code}`));
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      rejectRun(error);
    });
  });
}

function waitForProcessExit(child, name) {
  return new Promise((_, rejectExit) => {
    child.once("exit", (code, signal) => {
      rejectExit(new Error(`${name} exited before service became ready: code=${code ?? "null"} signal=${signal ?? "null"}`));
    });
    child.once("error", (error) => {
      rejectExit(error);
    });
  });
}

function mimeType(path) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
  }[extname(path).toLowerCase()] || "application/octet-stream";
}

function resolveStaticPath(requestUrl) {
  const url = new URL(requestUrl || "/", `http://${frontendHost}:${frontendPort}`);
  const relativePath = decodeURIComponent(url.pathname).replace(/^\/+/, "");
  const candidate = normalize(resolve(distDir, relativePath || "index.html"));
  if (!candidate.startsWith(`${distDir}${sep}`) && candidate !== distDir) {
    return resolve(distDir, "index.html");
  }
  if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  return resolve(distDir, "index.html");
}

function createStaticServer() {
  if (!existsSync(resolve(distDir, "index.html"))) {
    throw new Error(`Missing live e2e build output: ${resolve(distDir, "index.html")}`);
  }

  const server = createHttpServer((request, response) => {
    const filePath = resolveStaticPath(request.url);
    response.writeHead(200, { "Content-Type": mimeType(filePath) });
    createReadStream(filePath).pipe(response);
  });
  servers.add(server);
  return new Promise((resolveServer, rejectServer) => {
    server.once("error", rejectServer);
    server.listen(frontendPort, frontendHost, () => {
      logStatus(`Live frontend ready on http://${frontendHost}:${frontendPort}`);
      resolveServer(server);
    });
  });
}

function patchDistApiBaseUrl() {
  const assetDir = resolve(distDir, "assets");
  const candidates = [
    resolve(distDir, "index.html"),
    ...(existsSync(assetDir) ? readdirSync(assetDir)
      .filter((entry) => entry.endsWith(".js"))
      .map((entry) => resolve(assetDir, entry)) : []),
  ];
  let patchedFiles = 0;
  let liveFiles = 0;

  for (const filePath of candidates) {
    if (!existsSync(filePath) || !statSync(filePath).isFile()) continue;
    const source = readFileSync(filePath, "utf8");
    if (source.includes(liveApiBaseUrl)) {
      liveFiles += 1;
    }
    if (!source.includes(mockedApiBaseUrl)) continue;
    writeFileSync(filePath, source.replaceAll(mockedApiBaseUrl, liveApiBaseUrl));
    patchedFiles += 1;
  }

  if (patchedFiles === 0) {
    if (liveFiles > 0) {
      logStatus(`Live e2e build output already points at live API base URL: ${liveApiBaseUrl}`);
      return;
    }
    throw new Error(`Live e2e build output did not contain ${mockedApiBaseUrl}`);
  }
  logStatus(`Patched live API base URL in ${patchedFiles} dist file(s): ${liveApiBaseUrl}`);
}

async function waitForUrl(url, child, name, timeoutMs = 60_000) {
  const startedAt = Date.now();
  await Promise.race([
    waitForProcessExit(child, name),
    (async () => {
      while (Date.now() - startedAt < timeoutMs) {
        try {
          const response = await fetch(url);
          if (response.ok) return;
        } catch {
          // Keep polling until the service accepts connections.
        }
        await new Promise((resolvePoll) => setTimeout(resolvePoll, 500));
      }
      throw new Error(`Timed out waiting for ${url}`);
    })(),
  ]);
}

try {
  hardTimeout = setTimeout(() => {
    logStatus(`Live e2e hard timeout after ${liveE2eHardTimeoutMs}ms`);
    void cleanup().finally(() => {
      process.exit(124);
    });
  }, liveE2eHardTimeoutMs);

  await assertPortAvailable(backendPort, backendHost);
  await assertPortAvailable(frontendPort, frontendHost);

  patchDistApiBaseUrl();

  const backend = startManagedProcess("live-backend", nodeExecutable, [backendScript]);
  await waitForUrl(`http://${backendHost}:${backendPort}/docs`, backend, "live-backend");
  logStatus(`Live backend ready on http://${backendHost}:${backendPort}/docs`);

  await createStaticServer();
  await runPackageVersionLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Package validation live smoke completed: validated package promoted to ready version and accepted a deployment task");
  await runDeploymentPromotionLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Deployment promotion live smoke completed: pause/resume, impact preview, promote, rollback, and drain were verified");
  await runRunTriageLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Run triage live smoke completed: failed-run triage, replay comparison, and dataset evidence capture were verified");
  await runQualityLoopLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Quality loop live smoke completed: dataset capture, experiment run, quality gate preview, and promotion evidence were verified");
  await runEnterpriseOpsLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Enterprise ops live smoke completed: incident response, notification probe, backup preview, and restore guardrails were verified");
  await runPolicyApprovalLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Policy approval live smoke completed: simulate, activate, rollback, approve, and reject were verified");
  await runGatewayGovernanceLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Gateway governance live smoke completed: model gateway, tool, and secret workflows were verified");
  await runPublishedSurfaceLiveSmoke({
    frontendBaseUrl: `http://${frontendHost}:${frontendPort}`,
    apiBaseUrl: liveApiBaseUrl,
  });
  logStatus("Published surface live smoke completed: ingress accepted, exposure ready, revoke evidence observed");
} finally {
  if (children.size > 0 || servers.size > 0) {
    logStatus("Stopping live e2e services");
    await cleanup();
  }
}
