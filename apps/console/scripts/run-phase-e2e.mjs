import { spawnSync } from "node:child_process";
import { rmSync } from "node:fs";
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
const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const npxCommand = isWindows ? "npx.cmd" : "npx";
const outputIndex = playwrightArgs.findIndex((value) => value === "--output");
const outputDir = outputIndex >= 0 ? playwrightArgs[outputIndex + 1] : null;
const actualOutputDir =
  outputDir && outputIndex >= 0 ? `${outputDir}-${Date.now()}` : null;

if (outputDir) {
  try {
    rmSync(path.resolve(rootDir, outputDir), { force: true, recursive: true });
  } catch (error) {
    console.warn(`Failed to clean ${outputDir}:`, error);
  }
}
if (actualOutputDir && outputIndex >= 0) {
  playwrightArgs[outputIndex + 1] = actualOutputDir;
}

const commands = [
  [npmCommand, ["run", "check:e2e-browser"]],
  [
    npxCommand,
    [
      "playwright",
      "test",
      specPath,
      ...(playwrightArgs.length > 0 ? playwrightArgs : ["--project=chrome"]),
    ],
  ],
];

for (const [command, args] of commands) {
  const result = spawnSync(command, args, {
    cwd: rootDir,
    env: process.env,
    shell: isWindows,
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
