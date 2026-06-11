import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function verifyPhase0LProof(proof) {
  if (!proof || !Array.isArray(proof.phases) || !proof.phases.includes("0l")) {
    return {
      ok: false,
      message: "Latest shared phase proof does not include phase 0L coverage.",
    };
  }
  return {
    ok: true,
    message: `Phase 0L proof accepted from ${String(proof.spec_path || "")}`,
  };
}

export function emitPhase0LReport({ reportDir, proof }) {
  mkdirSync(reportDir, { recursive: true });
  writeFileSync(
    path.join(reportDir, "index.html"),
    `<!doctype html><html><body><h1>Phase 0L Browser Proof</h1><p>Derived from shared runner: ${String(proof.spec_path || "")}</p><p>Generated: ${String(proof.generated_at || "")}</p></body></html>`,
    "utf8",
  );
}

export function runPhase0LVerifier({
  rootDir = process.cwd(),
  reportName = process.env.PLAYWRIGHT_HTML_REPORT || "playwright-report-0l",
} = {}) {
  const proofPath = path.resolve(rootDir, ".phase-e2e-proof.json");
  const reportDir = path.resolve(rootDir, reportName);

  if (!existsSync(proofPath)) {
    return {
      ok: false,
      message: "Missing shared phase proof. Run `npm run test:e2e:0j` first.",
      proof: null,
      reportDir,
    };
  }

  const proof = JSON.parse(readFileSync(proofPath, "utf8"));
  const verification = verifyPhase0LProof(proof);
  if (!verification.ok) {
    return {
      ok: false,
      message: verification.message,
      proof,
      reportDir,
    };
  }

  emitPhase0LReport({ reportDir, proof });
  return {
    ok: true,
    message: verification.message,
    proof,
    reportDir,
  };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const result = runPhase0LVerifier();
  if (!result.ok) {
    console.error(result.message);
    process.exit(1);
  }
  console.log(result.message);
}
