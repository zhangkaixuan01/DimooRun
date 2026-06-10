import { spawnSync } from "node:child_process";
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

const commands = [
  [process.execPath, [path.join(rootDir, "scripts", "check-playwright-browser.mjs")]],
  [process.execPath, [path.join(rootDir, "node_modules", "vue-tsc", "bin", "vue-tsc.js"), "--noEmit"]],
  [process.execPath, [path.join(rootDir, "node_modules", "vite", "bin", "vite.js"), "build", "--mode", "e2e"]],
  [
    process.execPath,
    [
      path.join(rootDir, "node_modules", "@playwright", "test", "cli.js"),
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
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
