import { spawn } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const logDir = join(tmpdir(), "dimoorun-console-live-e2e");
const liveBackendPidFile = join(logDir, "live-backend-pids.json");
const backendPort = 4180;
const frontendPort = 4174;
const cleanupCommandTimeoutMs = 5_000;
const taskkillTimeoutMs = 5_000;

function logStatus(message) {
  console.log(message);
}

function uniqueNumbers(values) {
  return [...new Set(values
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0))];
}

async function killWithTaskkill(pid) {
  if (process.platform !== "win32") return;

  await new Promise((resolveKill) => {
    let child;
    try {
      child = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
        stdio: "ignore",
        shell: false,
      });
    } catch {
      resolveKill();
      return;
    }
    const timeout = setTimeout(() => {
      logStatus(`Taskkill timed out during live cleanup for process: ${pid}`);
      resolveKill();
    }, taskkillTimeoutMs);
    const finish = () => {
      clearTimeout(timeout);
      resolveKill();
    };
    child.on("exit", finish);
    child.on("error", finish);
  });
}

async function killPid(pid) {
  try {
    process.kill(pid);
  } catch {
    await killWithTaskkill(pid);
  }
}

async function cleanupPidFile() {
  if (!existsSync(liveBackendPidFile)) return;

  const payload = JSON.parse(readFileSync(liveBackendPidFile, "utf8"));
  const pids = uniqueNumbers([payload.uvicorn_worker_pid, payload.server_pid, payload.launcher_pid]);
  await Promise.allSettled(pids.map((pid) => killPid(pid)));
  rmSync(liveBackendPidFile, { force: true });
}

function commandOutput(command, args) {
  return new Promise((resolveOutput) => {
    let child;
    try {
      child = spawn(command, args, { stdio: ["ignore", "pipe", "pipe"], shell: false });
    } catch {
      resolveOutput("");
      return;
    }
    let stdout = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    const timeout = setTimeout(() => {
      logStatus(`Command output timed out during live cleanup: ${command} ${args.join(" ")}`);
      child.kill();
      resolveOutput(stdout);
    }, cleanupCommandTimeoutMs);
    const finish = (output) => {
      clearTimeout(timeout);
      resolveOutput(output);
    };
    child.on("exit", () => finish(stdout));
    child.on("error", () => finish(""));
  });
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

  await Promise.allSettled([...pids].map((pid) => killPid(pid)));
}

await cleanupPidFile();
await cleanupPortListeners();
