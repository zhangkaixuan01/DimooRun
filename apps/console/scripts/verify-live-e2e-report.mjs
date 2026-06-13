import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const defaultLogPath = join(tmpdir(), "dimoorun-console-live-e2e", "run-live-e2e.log");

export const requiredMarkers = [
  "Live backend ready on http://127.0.0.1:4180/docs",
  "Live frontend ready on http://127.0.0.1:4174",
  "Live smoke step: triage opened",
  "Live smoke step: replay comparison evidence captured",
  "Run triage live smoke completed",
  "Live smoke step: policy workbench simulated activation and rollback",
  "Live smoke step: human approval decisions captured with resume outcomes",
  "Policy approval live smoke completed",
  "Live smoke step: route test completed",
  "Live smoke step: request log opened",
  "Live smoke step: traffic split applied",
  "Live smoke step: rollback completed",
  "Published surface live smoke completed",
  "Stopping live e2e services",
];

export const failureMarkerList = [
  "Live e2e hard timeout",
  "spawn EPERM",
  "Live e2e smoke failed",
  "exited before service became ready",
];

export function parseArgs(argv) {
  const args = [...argv];
  const logFlagIndex = args.indexOf("--log");
  if (logFlagIndex >= 0) {
    const value = args[logFlagIndex + 1];
    if (!value) {
      throw new Error("Missing value after --log");
    }
    return { logPath: resolve(value) };
  }
  return { logPath: defaultLogPath };
}

export function missingMarkers(report) {
  return requiredMarkers.filter((marker) => !report.includes(marker));
}

export function outOfOrderMarkers(report) {
  const positions = requiredMarkers.map((marker) => report.indexOf(marker));
  const outOfOrder = [];

  for (let index = 1; index < positions.length; index += 1) {
    if (positions[index] < positions[index - 1]) {
      outOfOrder.push(requiredMarkers[index]);
    }
  }

  return outOfOrder;
}

export function failureMarkers(report) {
  return failureMarkerList.filter((marker) => report.includes(marker));
}

export function verifyReport(report) {
  const missing = missingMarkers(report);
  const outOfOrder = missing.length === 0 ? outOfOrderMarkers(report) : [];
  const failures = failureMarkers(report);
  return { missing, outOfOrder, failures, ok: missing.length === 0 && outOfOrder.length === 0 && failures.length === 0 };
}

function runCli() {
  try {
    const { logPath } = parseArgs(process.argv.slice(2));
    if (!existsSync(logPath)) {
      throw new Error(`Live e2e report does not exist: ${logPath}`);
    }

    const report = readFileSync(logPath, "utf8");
    const { missing, outOfOrder, failures, ok } = verifyReport(report);

    if (!ok) {
      if (missing.length > 0) {
        console.error(`Missing live e2e marker(s): ${missing.join(", ")}`);
      }
      if (outOfOrder.length > 0) {
        console.error(`Out-of-order live e2e marker(s): ${outOfOrder.join(", ")}`);
      }
      if (failures.length > 0) {
        console.error(`Live e2e failure marker(s): ${failures.join(", ")}`);
      }
      process.exitCode = 1;
    } else {
      console.log(`Live e2e report accepted: ${logPath}`);
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  runCli();
}
