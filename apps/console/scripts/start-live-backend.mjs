import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";

const checkOnly = process.argv.includes("--check");
const repoRoot = resolve(process.cwd(), "../..");
const databaseDir = join(tmpdir(), "dimoorun-console-live-e2e");
mkdirSync(databaseDir, { recursive: true });
const uvCacheDir = join(databaseDir, "uv-cache");
mkdirSync(uvCacheDir, { recursive: true });
const logPath = join(databaseDir, "start-live-backend.log");
const pidFilePath = process.env.DIMOORUN_LIVE_BACKEND_PID_FILE || "";
const fixtureFilePath = process.env.DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE || join(databaseDir, "live-gateway-fixture.json");
const backendHost = "127.0.0.1";
const backendPort = 4180;
const configuredCheckTimeoutMs = Number(process.env.DIMOORUN_LIVE_BACKEND_CHECK_TIMEOUT_MS);
const liveBackendCheckTimeoutMs =
  Number.isInteger(configuredCheckTimeoutMs) && configuredCheckTimeoutMs > 0
    ? configuredCheckTimeoutMs
    : 90_000;
const taskkillTimeoutMs = 5_000;

const databaseUrl =
  process.env.DATABASE_URL ||
  `sqlite:///${join(databaseDir, `dimoorun-live-${process.pid}.db`).replaceAll("\\", "/")}`;

const env = {
  ...process.env,
  DATABASE_URL: databaseUrl,
  REDIS_URL: process.env.REDIS_URL || "memory://console-live-e2e",
  DIMOORUN_RUNTIME_MODE: "dev",
  DIMOORUN_NATIVE_RUNTIME_STORE: process.env.DIMOORUN_NATIVE_RUNTIME_STORE || "sqlalchemy",
  DIMOORUN_BOOTSTRAP_ADMIN_EMAIL:
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_EMAIL || "admin@local.dimoorun",
  DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD:
    process.env.DIMOORUN_BOOTSTRAP_ADMIN_PASSWORD || "admin12345",
  DIMOORUN_CONSOLE_ACCESS_TOKEN_TTL_SECONDS: "43200",
  DIMOORUN_CORS_ORIGINS:
    process.env.DIMOORUN_CORS_ORIGINS ||
    "http://127.0.0.1:4174,http://localhost:4174",
  UV_CACHE_DIR: process.env.UV_CACHE_DIR || uvCacheDir,
  DIMOORUN_LIVE_GATEWAY_FIXTURE_FILE: fixtureFilePath,
};

const uvCommand = process.platform === "win32" ? "uv.exe" : "uv";
const children = new Set();

function logStatus(message) {
  console.log(message);
  appendFileSync(logPath, `[${new Date().toISOString()}] ${message}\n`);
}

function writePidFile(child) {
  if (!pidFilePath || !child.pid) return;

  updatePidFile({
    launcher_pid: process.pid,
    server_pid: child.pid,
    backend_port: backendPort,
    started_at: new Date().toISOString(),
  });
  logStatus(`Wrote live backend PID file: ${pidFilePath}`);
}

function updatePidFile(fields) {
  if (!pidFilePath) return;

  const current = existsSync(pidFilePath)
    ? JSON.parse(readFileSync(pidFilePath, "utf8"))
    : {};
  writeFileSync(pidFilePath, JSON.stringify({
    ...current,
    ...fields,
    updated_at: new Date().toISOString(),
  }, null, 2));
}

function track(child) {
  children.add(child);
  child.on("exit", () => {
    children.delete(child);
  });
  return child;
}

function assertPortAvailable(port, host = backendHost) {
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

function waitForChildExit(child, timeoutMs = 10_000) {
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
      logStatus(`Taskkill timed out for live backend process: ${child.pid}`);
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

async function cleanup() {
  const results = await Promise.allSettled([...children].map((child) => killChildTree(child)));
  for (const result of results) {
    if (result.status === "rejected") {
      logStatus(`Live backend cleanup warning: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`);
    }
  }
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    void cleanup().finally(() => {
      process.exit(130);
    });
  });
}

function run(command, args, timeoutMs = 45_000) {
  return new Promise((resolveProcess, rejectProcess) => {
    logStatus(`Starting ${command} ${args.join(" ")}`);
    const child = track(spawn(command, args, {
      cwd: repoRoot,
      env,
      shell: false,
      stdio: "inherit",
    }));
    const timeout = setTimeout(() => {
      void killChildTree(child);
      rejectProcess(new Error(`${command} ${args.join(" ")} timed out after ${timeoutMs}ms`));
    }, timeoutMs);
    child.on("exit", (code) => {
      clearTimeout(timeout);
      if (code === 0) resolveProcess();
      else rejectProcess(new Error(`${command} ${args.join(" ")} exited with ${code}`));
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      rejectProcess(error);
    });
  });
}

function startServer() {
  logStatus(`Starting uv run uvicorn dimoo_run.server:app on ${backendHost}:${backendPort}`);
  const child = track(spawn(
    uvCommand,
    ["run", "uvicorn", "dimoo_run.server:app", "--host", backendHost, "--port", String(backendPort)],
    {
      cwd: repoRoot,
      env,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    },
  ));
  child.stdout.on("data", (chunk) => {
    process.stdout.write(chunk);
    const output = chunk.toString();
    const match = output.match(/Started server process \[(\d+)\]/);
    if (match) {
      updatePidFile({ uvicorn_worker_pid: Number(match[1]) });
    }
  });
  child.stderr.on("data", (chunk) => {
    process.stderr.write(chunk);
    const output = chunk.toString();
    const match = output.match(/Started server process \[(\d+)\]/);
    if (match) {
      updatePidFile({ uvicorn_worker_pid: Number(match[1]) });
    }
  });
  writePidFile(child);
  return child;
}

async function waitForBackend(timeoutMs = 30_000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(`http://${backendHost}:${backendPort}/docs`);
      if (response.ok) return;
    } catch {
      // Keep polling until uvicorn accepts connections.
    }
    await new Promise((resolvePoll) => setTimeout(resolvePoll, 500));
  }
  throw new Error(`Timed out waiting for live backend on http://${backendHost}:${backendPort}/docs`);
}

await assertPortAvailable(backendPort);
await run(uvCommand, ["run", "python", "-m", "dimoo_run.ops.init_db"]);
await run(uvCommand, ["run", "python", "-m", "dimoo_run.ops.seed_live_gateway_fixture"]);

const server = startServer();

if (checkOnly) {
  const checkHardTimeout = setTimeout(() => {
    logStatus(`Live backend check hard timeout after ${liveBackendCheckTimeoutMs}ms`);
    void cleanup().finally(() => {
      process.exit(124);
    });
  }, liveBackendCheckTimeoutMs);
  try {
    await waitForBackend();
    logStatus(`Live backend check passed: http://${backendHost}:${backendPort}/docs`);
  } finally {
    clearTimeout(checkHardTimeout);
    logStatus("Backend ready, stopping live backend check server");
    await cleanup();
  }
} else {
  server.on("exit", (code) => {
    process.exit(code ?? 0);
  });

  server.on("error", (error) => {
    console.error(error);
    process.exit(1);
  });
}
