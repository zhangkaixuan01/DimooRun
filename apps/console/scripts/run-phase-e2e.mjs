import { spawn, spawnSync } from "node:child_process";
import http from "node:http";
import { cpSync, existsSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [, , specPath, ...playwrightArgs] = process.argv;

if (!specPath) {
  console.error(
    "Usage: node scripts/run-phase-e2e.mjs <spec-path> [playwright args...]",
  );
  process.exit(1);
}

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const playwrightCli = path.resolve(
  rootDir,
  "node_modules",
  "playwright",
  "cli.js",
);
const windowsCmd = process.env.ComSpec || "cmd.exe";
const outputIndex = playwrightArgs.findIndex((value) => value === "--output");
const outputDir = outputIndex >= 0 ? playwrightArgs[outputIndex + 1] : null;
const actualOutputDir =
  outputDir && outputIndex >= 0 ? `${outputDir}-${Date.now()}` : null;
const htmlReportDir = process.env.PLAYWRIGHT_HTML_REPORT || "playwright-report";
const actualHtmlReportDir = `${htmlReportDir}-${Date.now()}`;
const runtimeHtmlReportDir = process.platform === "win32" ? "playwright-report" : actualHtmlReportDir;
const serverHost = "127.0.0.1";
const serverPort = 4173;
const serverReadyUrl = `http://${serverHost}:${serverPort}`;
const distDir = path.resolve(rootDir, "dist");
const indexPath = path.resolve(distDir, "index.html");
const phaseProofPath = path.resolve(rootDir, ".phase-e2e-proof.json");
const useWindowsManagedCli = process.platform === "win32";
const childEnv = { ...process.env };

if (outputDir) {
  try {
    rmSync(path.resolve(rootDir, outputDir), { force: true, recursive: true });
  } catch (error) {
    console.warn(`Failed to clean ${outputDir}:`, error);
  }
}
try {
  rmSync(path.resolve(rootDir, htmlReportDir), { force: true, recursive: true });
} catch (error) {
  console.warn(`Failed to clean ${htmlReportDir}:`, error);
}
try {
  rmSync(phaseProofPath, { force: true });
} catch (error) {
  console.warn(`Failed to clean ${phaseProofPath}:`, error);
}
if (actualOutputDir && outputIndex >= 0) {
  playwrightArgs[outputIndex + 1] = actualOutputDir;
}

const commands = [
  [process.execPath, [path.resolve(rootDir, "scripts", "check-playwright-browser.mjs")]],
];

for (const [command, args] of commands) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    env: {
      ...childEnv,
      PLAYWRIGHT_HTML_REPORT: actualHtmlReportDir,
      ...(actualOutputDir ? { PLAYWRIGHT_OUTPUT_DIR: actualOutputDir } : {}),
    },
    shell: false,
    stdio: "inherit",
  });
  if (result.error) {
    console.error(result.error);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

let serverProcess = null;
let ownsServer = false;

try {
  if (!useWindowsManagedCli && !(await isServerReady())) {
    serverProcess = await startDistServer();
    ownsServer = true;
  }

  const result = await runPlaywrightWithRetries(
    useWindowsManagedCli
        ? {
          type: "spawn",
          command: windowsCmd,
          args: [
            "/d",
            "/s",
            "/c",
            quoteWindowsCommand([
              path.resolve(path.dirname(process.execPath), "npx.cmd"),
              "playwright",
              "test",
              specPath,
              ...(playwrightArgs.length > 0 ? playwrightArgs : ["--project=chrome"]),
            ]),
          ],
        }
      : {
          type: "spawn",
          command: process.execPath,
          args: [
            playwrightCli,
            "test",
            specPath,
            ...(playwrightArgs.length > 0 ? playwrightArgs : ["--project=chrome"]),
          ],
        },
    {
      cwd: rootDir,
      env: {
        ...childEnv,
        ...(!useWindowsManagedCli ? {
          DIMOORUN_E2E_SERVER_READY: "1",
          PLAYWRIGHT_HTML_REPORT: actualHtmlReportDir,
          ...(actualOutputDir ? { PLAYWRIGHT_OUTPUT_DIR: actualOutputDir } : {}),
        } : {}),
      },
      shell: false,
    },
  );
  if (result !== 0) {
    process.exit(result);
  }
  if (actualOutputDir && outputDir) {
    normalizeArtifactPath(path.resolve(rootDir, actualOutputDir), path.resolve(rootDir, outputDir));
  }
  normalizeArtifactPath(path.resolve(rootDir, runtimeHtmlReportDir), path.resolve(rootDir, htmlReportDir));
  writePhaseProof({
    specPath,
    outputDir: outputDir || actualOutputDir,
    htmlReportDir,
  });
} finally {
  if (ownsServer && serverProcess) {
    await stopServer(serverProcess);
  }
}

async function isServerReady() {
  try {
    const response = await fetch(serverReadyUrl);
    return response.ok;
  } catch {
    return false;
  }
}

async function startDistServer() {
  if (!existsSync(indexPath)) {
    throw new Error("Missing dist/index.html. Run `npm run build:e2e` first.");
  }

  const server = http.createServer((request, response) => {
    const url = new URL(request.url || "/", serverReadyUrl);
    let filePath = path.join(
      distDir,
      url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1)),
    );
    if (!filePath.startsWith(distDir)) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }
    if (!existsSync(filePath) || statSafe(filePath)?.isDirectory()) {
      filePath = indexPath;
    }
    const ext = path.extname(filePath);
    const body = readFileSync(filePath);
    response.writeHead(200, {
      "Content-Type": contentType(ext),
      "Cache-Control": "no-cache",
    });
    response.end(body);
  });

  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(serverPort, serverHost, () => {
      server.off("error", reject);
      console.log(`Console dist server ready on ${serverReadyUrl}`);
      resolve(undefined);
    });
  });

  return server;
}

async function stopServer(server) {
  await new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve(undefined);
    });
  });
}

function statSafe(filePath) {
  try {
    return statSync(filePath);
  } catch {
    return null;
  }
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

function writePhaseProof({ specPath: executedSpecPath, outputDir: executedOutputDir, htmlReportDir: executedHtmlReportDir }) {
  const phases = [];
  if (executedSpecPath.endsWith("runtime-capacity.spec.ts")) {
    phases.push("0j", "0l");
  }
  if (executedSpecPath.endsWith("published-surfaces.spec.ts")) {
    phases.push("0h");
  }
  if (executedSpecPath.endsWith("compatibility-explorer.spec.ts")) {
    phases.push("0i");
  }
  if (executedSpecPath.endsWith("costs-budgets.spec.ts")) {
    phases.push("0m");
  }
  if (executedSpecPath.endsWith("scheduled-batch.spec.ts")) {
    phases.push("0n");
  }
  if (executedSpecPath.endsWith("catalog-assets.spec.ts")) {
    phases.push("0o");
  }
  if (phases.length === 0) {
    return;
  }
  writeFileSync(
    phaseProofPath,
    JSON.stringify(
      {
        spec_path: executedSpecPath,
        output_dir: executedOutputDir || null,
        html_report_dir: executedHtmlReportDir,
        phases,
        generated_at: new Date().toISOString(),
      },
      null,
      2,
    ),
    "utf8",
  );
}

async function runPlaywrightWithRetries(commandSpec, options) {
  const maxAttempts = 3;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const outcome = await runStreamingCommand(
        commandSpec.command,
        commandSpec.args,
        {
          ...options,
          shell: commandSpec.shell ?? options.shell,
        },
      );
      if (outcome.code === 0) {
        return 0;
      }
      if (!outcome.output.includes("spawn EPERM") || attempt === maxAttempts) {
        return outcome.code;
      }
    } catch (error) {
      if (!(error instanceof Error) || !String(error.message).includes("spawn EPERM") || attempt === maxAttempts) {
        throw error;
      }
    }
    console.warn(`Playwright worker spawn hit EPERM on attempt ${attempt}; retrying.`);
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  return 1;
}

async function runStreamingCommand(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  return await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.stdout?.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stdout.write(text);
    });
    child.stderr?.on("data", (chunk) => {
      const text = chunk.toString();
      output += text;
      process.stderr.write(text);
    });
    child.once("exit", (code) => resolve({ code: code ?? 1, output }));
  });
}

function quoteWindowsCommand(parts) {
  return parts
    .map((part) => {
      const text = String(part);
      if (text.length === 0) {
        return '""';
      }
      if (!/[\s"]/u.test(text)) {
        return text;
      }
      return `"${text.replace(/"/g, '\\"')}"`;
    })
    .join(" ");
}


function normalizeArtifactPath(sourcePath, targetPath) {
  if (!existsSync(sourcePath)) {
    return;
  }
  if (path.resolve(sourcePath) === path.resolve(targetPath)) {
    return;
  }
  try {
    rmSync(targetPath, { force: true, recursive: true });
  } catch (error) {
    console.warn(`Failed to clean ${targetPath}:`, error);
  }
  try {
    renameSync(sourcePath, targetPath);
  } catch {
    cpSync(sourcePath, targetPath, { recursive: true });
    rmSync(sourcePath, { force: true, recursive: true });
  }
}
