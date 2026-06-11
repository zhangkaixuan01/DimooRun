import { mkdtempSync, readFileSync, existsSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import assert from "node:assert/strict";

const root = fileURLToPath(new URL("..", import.meta.url));
const phase0LVerifier = await import("../scripts/verify-phase-0l-proof.mjs");

function read(path) {
  return readFileSync(join(root, path), "utf8");
}

function listVueFiles(dir) {
  return readdirSync(join(root, dir)).flatMap((entry) => {
    const full = join(dir, entry);
    const stat = statSync(join(root, full));
    if (stat.isDirectory()) return listVueFiles(full);
    return full.endsWith(".vue") ? [full] : [];
  });
}

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test("declares the MVP runtime control routes", () => {
    const router = read("src/router/index.ts");
    [
      "/dashboard",
      "/agents",
      "/deployments",
      "/compatibility",
      "/published-surfaces",
      "/runtime/workers",
      "/runtime/agent-instances",
      "/runtime/capacity",
      "/runs",
      "/runs/:runId",
      "/tasks",
      "/events",
      "/replay",
      "/governance/human-tasks",
      "/governance/policies",
      "/governance/api-keys",
      "/settings",
    ].forEach((route) => assert.match(router, new RegExp(route.replaceAll("/", "\\/"))));
});

test("keeps language and theme as explicit user preferences", () => {
    const preferences = read("src/stores/preferences.ts");
    assert.match(preferences, /zh-CN/);
    assert.match(preferences, /en-US/);
    assert.match(preferences, /light/);
    assert.match(preferences, /dark/);
    assert.match(preferences, /localStorage/);
});

test("ships Chinese and English copy for the console shell", () => {
    const messages = read("src/i18n/messages.ts");
    assert.match(messages, /zh-CN/);
    assert.match(messages, /en-US/);
    assert.match(messages, /Runtime Control Plane/);
    assert.match(messages, /运行控制平面/);
});

test("keeps user-facing console copy behind i18n messages", () => {
    const messages = read("src/i18n/messages.ts");
    const zhKeys = [...messages.matchAll(/    ([a-zA-Z][a-zA-Z0-9]*):/g)].map((match) => match[1]);
    assert.ok(zhKeys.includes("dashboardCopy"));
    assert.ok(zhKeys.includes("replayComparison"));
    assert.ok(zhKeys.includes("apiKeysCopy"));

    const vueSource = listVueFiles("src").map((path) => read(path)).join("\n");
    [
      "Runtime health, cost, queue pressure",
      "Register Agent",
      "Create replay",
      "Replay comparison",
      "Create API Key",
      "Search run id or agent",
      "Time range",
      "Run trend chart",
      "Selected event",
      "Metadata / Cost",
      "All queues",
      "Console preferences",
    ].forEach((literal) => assert.equal(vueSource.includes(literal), false, literal));
});

test("has theme tokens for light and dark console styles", () => {
    const tokens = read("src/styles/tokens.css");
    assert.match(tokens, /\[data-theme="light"\]/);
    assert.match(tokens, /\[data-theme="dark"\]/);
    assert.match(tokens, /--color-surface/);
    assert.match(tokens, /--color-danger/);
});

test("renders high-risk operation confirmation with audit impact", () => {
    const dialogPath = "src/components/ConfirmImpactDialog.vue";
    assert.equal(existsSync(join(root, dialogPath)), true);
    const dialog = read(dialogPath);
    assert.match(dialog, /impactTarget/);
    assert.match(dialog, /affectsNewRuns/);
    assert.match(dialog, /affectsExistingRuns/);
    assert.match(dialog, /writesAuditLog/);
    assert.match(dialog, /rollbackable/);
});

test("uses a typed Native API client as the console backend boundary", () => {
    const generatedClientPath = "src/api/generated/dimoorun.ts";
    assert.equal(existsSync(join(root, generatedClientPath)), true);
    const generatedClient = read(generatedClientPath);
    const consoleClient = read("src/api/client.ts");

    assert.match(generatedClient, /createDimooRunClient/);
    assert.match(generatedClient, /NativeDeploymentRead/);
    assert.match(generatedClient, /\/v1\/deployments/);
    assert.match(consoleClient, /createDimooRunClient/);
    assert.match(consoleClient, /mapNativeDeployment/);
});

test("persists the bearer session token returned by login", () => {
    const authStore = read("src/stores/auth.ts");
    assert.match(authStore, /payload\.access_token/);
    assert.doesNotMatch(authStore, /setItem\(TOKEN_KEY,\s*"cookie"\)/);
});

test("parses FastAPI HTTPException detail errors", () => {
    const generatedClient = read("src/api/generated/dimoorun.ts");
    assert.match(generatedClient, /payload\?\.detail\?\.message/);
    assert.match(generatedClient, /payload\?\.detail\?\.error_code/);
    assert.match(generatedClient, /payload\?\.detail\?\.request_id/);
});

test("shows real run detail payloads and attempts instead of sample data", () => {
    const types = read("src/api/types.ts");
    const client = read("src/api/client.ts");
    const runDetail = read("src/pages/runs/RunDetailPage.vue");

    assert.match(types, /export type RunAttempt/);
    assert.match(types, /input\?: Record<string, unknown>/);
    assert.match(types, /output\?: Record<string, unknown> \| null/);
    assert.match(types, /error\?: Record<string, unknown> \| null/);

    assert.match(client, /listRunAttempts/);
    assert.match(client, /mapNativeRunAttempt/);
    assert.match(client, /input: run\.input/);
    assert.match(client, /output: run\.output/);
    assert.match(client, /error: run\.error/);

    assert.match(runDetail, /consoleClient\.listRunAttempts\(runId\.value\)/);
    assert.match(runDetail, /attempts\.value/);
    assert.match(runDetail, /formatJson\(currentRun\.input/);
    assert.match(runDetail, /formatJson\(currentRun\.output/);
    assert.match(runDetail, /formatJson\(currentRun\.error/);
    assert.doesNotMatch(runDetail, /ticket_id/);
    assert.doesNotMatch(runDetail, /POLICY_APPROVAL_REQUIRED/);
});

test("uses live frontend data instead of fake runtime values", () => {
    const client = read("src/api/client.ts");
    const types = read("src/api/types.ts");
    const dashboard = read("src/pages/dashboard/DashboardPage.vue");
    const chart = read("src/components/RuntimeTrendChart.vue");

    assert.match(types, /startedAt: string \| null/);
    assert.match(types, /timestamp\?: string/);
    assert.doesNotMatch(client, /latencyMs: 0/);
    assert.doesNotMatch(client, /costUsd: 0/);
    assert.doesNotMatch(client, /startedAt: new Date\(\)\.toISOString\(\)/);
    assert.doesNotMatch(client, /timestamp: new Date\(\)\.toISOString\(\)/);

    assert.match(chart, /defineProps/);
    assert.match(chart, /trendPoints/);
    assert.match(dashboard, /trendPoints/);
    assert.match(client, /requestConsolePath<ConsoleRuntimeOverviewResponse>\("\/v1\/console\/runtime-overview"\)/);
    assert.match(client, /requestConsolePath<Record<string, unknown>>\("\/v1\/runtime\/metrics\/summary"\)/);
    assert.match(client, /overview\.trend_points/);
    assert.doesNotMatch(client, /recent_failures\.slice\(-12\)/);
    assert.doesNotMatch(dashboard, /v-if="mode === 'demo'"/);
});

test("wires operational filtering and event selection interactions", () => {
    const tasks = read("src/pages/tasks/TasksPage.vue");
    const runs = read("src/pages/runs/RunsPage.vue");
    const runDetail = read("src/pages/runs/RunDetailPage.vue");
    const timeline = read("src/components/EventTimeline.vue");
    const eventsPage = read("src/pages/events/EventsPage.vue");
    const types = read("src/api/types.ts");
    const client = read("src/api/client.ts");

    assert.match(tasks, /v-model="queueFilter"/);
    assert.match(tasks, /v-model="statusFilter"/);
    assert.match(tasks, /filteredTasks/);
    assert.match(tasks, /v-for="task in filteredTasks"/);
    assert.match(tasks, /openTaskDetail/);
    assert.match(tasks, /detailTask/);

    assert.match(runs, /openRunActionConfirm/);
    assert.match(runs, /runConfirmedRunAction/);
    assert.match(runs, /DangerConfirmDialog/);
    assert.doesNotMatch(runs, /@click="consoleClient\.controlRun/);

    assert.match(timeline, /defineEmits/);
    assert.match(timeline, /selectedEventId/);
    assert.match(runDetail, /@select="selectEvent"/);
    assert.match(runDetail, /selectedEventId/);
    assert.match(eventsPage, /@select="selectEvent"/);
    assert.match(eventsPage, /selectedEventId/);
    assert.match(eventsPage, /selectedEvent/);
    assert.match(types, /runId: ResourceId/);
    assert.match(client, /runId: event\.run_id/);
});

test("turns replay into a real console workflow", () => {
    const replay = read("src/pages/replay/ReplayPage.vue");
    const generatedClient = read("src/api/generated/dimoorun.ts");
    const consoleClient = read("src/api/client.ts");

    assert.match(replay, /consoleClient\.listRuns\(\)/);
    assert.match(replay, /selectedAgentVersionId/);
    assert.match(replay, /consoleClient\.replayRun/);
    assert.match(replay, /v-model(?:\.number)?="selectedRunId"/);
    assert.match(replay, /v-model(?:\.number)?="selectedAgentVersionId"/);
    assert.match(replay, /replayResult/);
    assert.match(replay, /ResourceLink/);
    assert.match(generatedClient, /replayRun/);
    assert.match(generatedClient, /agent_version_id/);
    assert.match(consoleClient, /replayRun/);
    assert.doesNotMatch(replay, /consoleClient\.controlRun\(selectedRunId, "replay"\)/);
    assert.doesNotMatch(replay, /run_01HX9KB6W4/);
    assert.doesNotMatch(replay, /support-agent@0\.3\.3-rc1/);
    assert.doesNotMatch(replay, /POLICY_APPROVAL_REQUIRED/);
    assert.doesNotMatch(replay, /approval_request_created/);
});

test("maps native lifecycle fields into runtime views", () => {
    const generatedClient = read("src/api/generated/dimoorun.ts");
    const types = read("src/api/types.ts");
    const client = read("src/api/client.ts");
    const runsPage = read("src/pages/runs/RunsPage.vue");
    const runDetail = read("src/pages/runs/RunDetailPage.vue");

    assert.match(generatedClient, /created_at: string/);
    assert.match(generatedClient, /started_at: string \| null/);
    assert.match(generatedClient, /finished_at: string \| null/);
    assert.match(generatedClient, /latency_ms: number \| null/);
    assert.match(types, /createdAt: string/);
    assert.match(types, /startedAt: string \| null/);
    assert.match(types, /finishedAt: string \| null/);
    assert.match(client, /createdAt: run\.created_at/);
    assert.match(client, /startedAt: run\.started_at/);
    assert.match(client, /finishedAt: run\.finished_at/);
    assert.match(client, /latencyMs: run\.latency_ms/);
    assert.match(runsPage, /formatDateTime\(run\.createdAt\)/);
    assert.match(runDetail, /formatDateTime\(currentRun\.startedAt\)/);
});

test("uses live-only Console data in product paths", () => {
    const client = read("src/api/client.ts");
    const env = read("src/env.d.ts");

    assert.doesNotMatch(client, /from "\.\/mockData"/);
    assert.doesNotMatch(client, /demoConsoleClient/);
    assert.doesNotMatch(client, /VITE_DIMOORUN_DEMO_MODE/);
    assert.match(client, /export const consoleClient = liveConsoleClient/);
    assert.doesNotMatch(env, /VITE_DIMOORUN_DEMO_MODE/);
});

test("exposes the production deployment task flow from the Console", () => {
    const generatedClient = read("src/api/generated/dimoorun.ts");
    const consoleClient = read("src/api/client.ts");
    const agentsPage = read("src/pages/agents/AgentsPage.vue");
    const deploymentsPage = read("src/pages/deployments/DeploymentsPage.vue");
    const publishedPage = read("src/pages/published/PublishedSurfacesPage.vue");
    const router = read("src/router/index.ts");
    const shell = read("src/layouts/AppShell.vue");

    assert.match(generatedClient, /NativeAgentVersionRead/);
    assert.match(generatedClient, /createAgentVersion/);
    assert.match(generatedClient, /listAgentVersions/);
    assert.match(generatedClient, /updateAgentVersion/);
    assert.match(generatedClient, /archiveAgentVersion/);
    assert.match(generatedClient, /createDeployment/);
    assert.match(generatedClient, /createDeploymentTask/);
    assert.match(consoleClient, /createAgentVersion/);
    assert.match(consoleClient, /listAgentVersions/);
    assert.match(consoleClient, /updateAgentVersion/);
    assert.match(consoleClient, /archiveAgentVersion/);
    assert.match(consoleClient, /createDeployment/);
    assert.match(consoleClient, /createDeploymentTask/);
    assert.match(agentsPage, /versionForm/);
    assert.match(agentsPage, /editVersionForm/);
    assert.match(agentsPage, /openEditVersionDrawer/);
    assert.match(agentsPage, /openArchiveVersionConfirm/);
    assert.match(agentsPage, /runConfirmedArchiveVersion/);
    assert.match(agentsPage, /v-for="version in versions"/);
    assert.doesNotMatch(agentsPage, /submitTask/);
    assert.doesNotMatch(agentsPage, /taskInputJson/);
    assert.match(deploymentsPage, /deploymentForm/);
    assert.match(deploymentsPage, /editDeploymentForm/);
    assert.match(deploymentsPage, /class="deployment-row"/);
    assert.match(deploymentsPage, /selectedDeployment/);
    assert.match(deploymentsPage, /activeDetailTab/);
    assert.match(deploymentsPage, /createOpen/);
    assert.match(deploymentsPage, /deploymentTaskInputJson/);
    assert.match(deploymentsPage, /deploymentTaskThreadId/);
    assert.match(deploymentsPage, /submitDeploymentTask/);
    assert.match(deploymentsPage, /updateDeployment/);
    assert.match(deploymentsPage, /archiveDeployment/);
    assert.match(deploymentsPage, /DangerConfirmDialog/);
    assert.match(deploymentsPage, /ResourceLink/);
    assert.match(publishedPage, /class="surface-row"/);
    assert.match(publishedPage, /defineProps<\{\s*surfaceId\?: string/);
    assert.match(publishedPage, /selectedSurface/);
    assert.match(publishedPage, /Number\(props\.surfaceId\)/);
    assert.match(publishedPage, /routesForSurface/);
    assert.match(publishedPage, /createAdminItem\("\/v1\/ingress-routes"/);
    assert.match(publishedPage, /consoleClient\.validatePublishedSurface/);
    assert.match(publishedPage, /consoleClient\.publishSurface/);
    assert.match(publishedPage, /consoleClient\.testIngressRoute/);
    assert.match(publishedPage, /consoleClient\.getPublishedSurfaceDetail/);
    assert.match(publishedPage, /consoleClient\.rolloutPublishedSurface/);
    [
      "Validate publish",
      "Publish surface",
      "Test route",
      "Open request log",
      "Apply traffic split",
      "Revoke surface",
      "Confirm revoke",
      "Rollback surface",
    ].forEach((literal) => assert.match(publishedPage, new RegExp(literal)));
    assert.match(router, /path: "\/published-surfaces\/:surfaceId"/);
    assert.match(router, /path: "\/published-surfaces\/ingress-routes", redirect: "\/published-surfaces"/);
    assert.doesNotMatch(shell, /to: "\/published-surfaces\/ingress-routes"/);
});

test("mocks the governed published surface browser workflow", () => {
    const fixture = read("tests/fixtures/api.ts");
    [
      'path === "/v1/published-surfaces/validate"',
      'path === "/v1/published-surfaces/publish"',
      'path === "/v1/ingress-routes/test"',
      "publishedDetailMatch",
      "publishedRolloutMatch",
    ].forEach((literal) => assert.match(fixture, new RegExp(literal.replaceAll("/", "\\/"))));
});

test("allows a locally supplied Chrome executable for browser workflow proof", () => {
    const config = read("playwright.config.ts");
    assert.match(config, /DIMOORUN_PLAYWRIGHT_CHROME/);
    assert.match(config, /executablePath/);
});

test("documents Playwright browser setup for cloned workspaces", () => {
    const packageJson = read("package.json");
    const readmePath = "README.md";
    const envExamplePath = ".env.e2e.example";
    const checkScriptPath = "scripts/check-playwright-browser.mjs";
    assert.equal(existsSync(join(root, readmePath)), true);
    assert.equal(existsSync(join(root, envExamplePath)), true);
    assert.equal(existsSync(join(root, checkScriptPath)), true);

    const readme = read(readmePath);
    const envExample = read(envExamplePath);
    const checkScript = read(checkScriptPath);
    const config = read("playwright.config.ts");
    assert.match(packageJson, /"check:e2e-browser"/);
    assert.match(readme, /npx playwright install chromium/);
    assert.match(readme, /\.env\.e2e\.local/);
    assert.match(readme, /DIMOORUN_PLAYWRIGHT_CHROME/);
    assert.match(readme, /chrome-win64\\chrome\.exe/);
    assert.match(envExample, /DIMOORUN_PLAYWRIGHT_CHROME=/);
    assert.match(checkScript, /DIMOORUN_PLAYWRIGHT_CHROME/);
    assert.match(checkScript, /\.env\.e2e\.local/);
    assert.match(checkScript, /npx playwright install chromium/);
    assert.match(config, /\.env\.e2e\.local/);
});

test("defines a live-backend published surface browser proof path", () => {
    const packageJson = read("package.json");
    const liveConfigPath = "playwright.live.config.ts";
    const liveSpecPath = "tests/e2e-live/published-surfaces-live.spec.ts";
    const liveRunnerPath = "scripts/run-live-e2e.mjs";
    const liveSmokePath = "scripts/published-surface-live-smoke.mjs";
    const liveCleanupPath = "scripts/cleanup-live-e2e.mjs";
    const liveLocalRunnerPath = "scripts/run-live-e2e-local.ps1";
    const liveReportVerifierPath = "scripts/verify-live-e2e-report.mjs";
    assert.equal(existsSync(join(root, liveConfigPath)), true);
    assert.equal(existsSync(join(root, liveSpecPath)), true);
    assert.equal(existsSync(join(root, liveRunnerPath)), true);
    assert.equal(existsSync(join(root, liveSmokePath)), true);
    assert.equal(existsSync(join(root, liveCleanupPath)), true);
    assert.equal(existsSync(join(root, liveLocalRunnerPath)), true);
    assert.equal(existsSync(join(root, liveReportVerifierPath)), true);

    const liveConfig = read(liveConfigPath);
    const liveSpec = read(liveSpecPath);
    const liveRunner = read(liveRunnerPath);
    const liveSmoke = read(liveSmokePath);
    const liveCleanup = read(liveCleanupPath);
    const liveLocalRunner = read(liveLocalRunnerPath);
    const liveReportVerifier = read(liveReportVerifierPath);
    assert.match(packageJson, /"test:e2e:live"/);
    assert.match(packageJson, /"test:e2e:live": "node scripts\/check-playwright-browser\.mjs && node scripts\/run-live-e2e\.mjs"/);
    assert.match(packageJson, /"test:e2e:live:local"/);
    assert.match(packageJson, /run-live-e2e-local\.ps1/);
    assert.match(packageJson, /"verify:e2e:live-report"/);
    assert.match(packageJson, /verify-live-e2e-report\.mjs/);
    assert.match(packageJson, /"cleanup:e2e:live": "node scripts\/cleanup-live-e2e\.mjs"/);
    assert.match(packageJson, /run-live-e2e\.mjs/);
    assert.match(liveConfig, /playwright-live-results/);
    assert.doesNotMatch(liveConfig, /webServer:/);
    assert.match(liveRunner, /start-live-backend\.mjs/);
    assert.doesNotMatch(liveRunner, /build:e2e/);
    assert.match(liveRunner, /patchDistApiBaseUrl/);
    assert.match(liveRunner, /http:\/\/127\.0\.0\.1:4173\/mock-api/);
    assert.match(liveRunner, /http:\/\/\$\{backendHost\}:\$\{backendPort\}/);
    assert.match(liveRunner, /already points at live API base URL/);
    assert.match(liveRunner, /patchDistApiBaseUrl\(\);\s*const backend = startManagedProcess/s);
    assert.match(liveRunner, /liveE2eEnv/);
    assert.match(liveRunner, /createStaticServer/);
    assert.match(liveRunner, /dist/);
    assert.doesNotMatch(liveRunner, /node_modules", "@playwright", "test", "cli\.js/);
    assert.match(liveRunner, /runPublishedSurfaceLiveSmoke/);
    assert.match(liveRunner, /Published surface live smoke completed/);
    assert.match(liveSmoke, /export async function runPublishedSurfaceLiveSmoke/);
    assert.match(liveSmoke, /chromium\.launch/);
    assert.match(liveSmoke, /DIMOORUN_PLAYWRIGHT_CHROME/);
    assert.match(liveRunner, /VITE_DIMOORUN_API_BASE_URL/);
    assert.match(liveRunner, /backendHost = "127\.0\.0\.1"/);
    assert.match(liveRunner, /backendPort = 4180/);
    assert.doesNotMatch(liveRunner, /vite-e2e/);
    assert.match(liveRunner, /resolveStaticPath/);
    assert.match(liveRunner, /index\.html/);
    assert.match(liveRunner, /exited before .* became ready/);
    assert.match(liveRunner, /Cleanup warning/);
    assert.match(liveRunner, /Promise\.allSettled/);
    assert.match(liveRunner, /await cleanup\(\)/);
    assert.match(liveRunner, /liveE2eHardTimeoutMs/);
    assert.match(liveRunner, /DIMOORUN_LIVE_E2E_TIMEOUT_MS/);
    assert.match(liveRunner, /Taskkill timed out/);
    assert.match(liveRunner, /liveBackendPidFile/);
    assert.match(liveRunner, /cleanupLiveBackendPidFile/);
    assert.match(liveRunner, /process\.kill\(pid/);
    assert.match(liveRunner, /function cleanupPortListeners/);
    assert.match(liveRunner, /netstat/);
    assert.match(liveRunner, /Listening port cleanup warning/);
    assert.doesNotMatch(liveRunner, /playwright\.live\.config\.ts/);
    assert.match(liveSmoke, /\/v1\/ingress\/support\/triage/);
    assert.match(liveSmoke, /Open request log/);
    assert.match(liveSmoke, /authorization: \[REDACTED\]/);
    assert.match(liveSmoke, /Apply traffic split/);
    assert.match(liveSmoke, /traffic_split/);
    assert.match(liveSmoke, /candidate: 20/);
    assert.match(liveSmoke, /logStep\("route test completed"\)/);
    assert.match(liveSmoke, /logStep\("request log opened"\)/);
    assert.match(liveSmoke, /logStep\("traffic split applied"\)/);
    assert.match(liveSmoke, /Exposure health: ready/);
    assert.match(liveSmoke, /published_surface\.revoke/);
    assert.match(liveSmoke, /Rollback surface/);
    assert.match(liveSmoke, /fetchSurfaceDetail/);
    assert.match(liveSmoke, /rollout_history\.at\(-1\)\?\.rollback_to_version/);
    assert.match(liveSmoke, /logStep\("rollback completed"\)/);
    assert.match(liveCleanup, /live-backend-pids\.json/);
    assert.match(liveCleanup, /process\.kill\(pid/);
    assert.match(liveCleanup, /backendPort = 4180/);
    assert.match(liveCleanup, /frontendPort = 4174/);
    assert.match(liveCleanup, /cleanupCommandTimeoutMs/);
    assert.match(liveCleanup, /taskkillTimeoutMs/);
    assert.match(liveCleanup, /Taskkill timed out during live cleanup/);
    assert.match(liveCleanup, /Command output timed out during live cleanup/);
    assert.match(liveCleanup, /clearTimeout\(timeout\)/);
    assert.match(liveLocalRunner, /npm run check:e2e-browser/);
    assert.match(liveLocalRunner, /npm run build:e2e/);
    assert.match(liveLocalRunner, /node scripts\/run-live-e2e\.mjs/);
    assert.match(liveLocalRunner, /npm run verify:e2e:live-report/);
    assert.match(liveLocalRunner, /npm run cleanup:e2e:live/);
    assert.match(liveLocalRunner, /finally/);
    assert.match(liveLocalRunner, /DIMOORUN_LIVE_E2E_TIMEOUT_MS/);
    assert.match(liveLocalRunner, /real terminal/);
    assert.doesNotMatch(liveLocalRunner, /Start-Process/);
    assert.doesNotMatch(liveLocalRunner, /RedirectStandardOutput/);
    assert.match(liveReportVerifier, /Live backend ready on http:\/\/127\.0\.0\.1:4180\/docs/);
    assert.match(liveReportVerifier, /Live frontend ready on http:\/\/127\.0\.0\.1:4174/);
    assert.match(liveReportVerifier, /Published surface live smoke completed/);
    assert.match(liveReportVerifier, /Live smoke step: route test completed/);
    assert.match(liveReportVerifier, /Live smoke step: request log opened/);
    assert.match(liveReportVerifier, /Live smoke step: traffic split applied/);
    assert.match(liveReportVerifier, /Live smoke step: rollback completed/);
    assert.match(liveReportVerifier, /Stopping live e2e services/);
    assert.match(liveReportVerifier, /Live e2e hard timeout/);
    assert.match(liveReportVerifier, /spawn EPERM/);
    assert.match(liveReportVerifier, /process\.exitCode = 1/);
    assert.match(liveSpec, /\/v1\/ingress\/support\/triage/);
    assert.match(liveSpec, /Exposure health: ready/);
    assert.match(liveSpec, /published_surface\.revoke/);
});

test("cleans up live-backend child process trees on Windows", () => {
    const liveBackendScript = read("scripts/start-live-backend.mjs");

    assert.match(liveBackendScript, /function waitForChildExit/);
    assert.match(liveBackendScript, /function assertPortAvailable/);
    assert.match(liveBackendScript, /function logStatus/);
    assert.match(liveBackendScript, /start-live-backend\.log/);
    assert.match(liveBackendScript, /DIMOORUN_LIVE_BACKEND_PID_FILE/);
    assert.match(liveBackendScript, /function writePidFile/);
    assert.match(liveBackendScript, /function updatePidFile/);
    assert.match(liveBackendScript, /Started server process/);
    assert.match(liveBackendScript, /uvicorn_worker_pid/);
    assert.match(liveBackendScript, /is already in use on/);
    assert.match(liveBackendScript, /function killChildTree/);
    assert.match(liveBackendScript, /DIMOORUN_LIVE_BACKEND_CHECK_TIMEOUT_MS/);
    assert.match(liveBackendScript, /liveBackendCheckTimeoutMs/);
    assert.match(liveBackendScript, /clearTimeout\(checkHardTimeout\)/);
    assert.match(liveBackendScript, /Taskkill timed out for live backend process/);
    assert.match(liveBackendScript, /taskkillTimeoutMs/);
    assert.match(liveBackendScript, /Backend ready, stopping live backend check server/);
    assert.match(liveBackendScript, /Timed out waiting for child process to exit/);
    assert.match(liveBackendScript, /process\.platform === "win32"/);
    assert.match(liveBackendScript, /taskkill/);
    assert.match(liveBackendScript, /\/T/);
    assert.match(liveBackendScript, /\/F/);
    assert.match(liveBackendScript, /\/PID/);
    assert.match(liveBackendScript, /await waitForChildExit\(child\)/);
    assert.match(liveBackendScript, /await cleanup\(\)/);
});

test("opens an agent registration form before creating an Agent", () => {
    const types = read("src/api/types.ts");
    const client = read("src/api/client.ts");
    const agentsPage = read("src/pages/agents/AgentsPage.vue");
    const generatedClient = read("src/api/generated/dimoorun.ts");

    const agentType = types.slice(types.indexOf("export type Agent = {"), types.indexOf("export type AgentVersion = {"));
    const agentMapper = client.slice(client.indexOf("function mapNativeAgent("), client.indexOf("function mapNativeAgentVersion("));
    assert.doesNotMatch(agentType, /framework/);
    assert.doesNotMatch(agentType, /adapter/);
    assert.doesNotMatch(agentType, /\n\s+version:/);
    assert.doesNotMatch(agentType, /capabilities/);
    assert.match(agentType, /status: string/);
    assert.match(agentType, /createdAt: string \| null/);
    assert.match(agentType, /versionCount: number/);
    assert.match(agentType, /deploymentCount: number/);
    assert.doesNotMatch(agentMapper, /framework: "LangGraph"/);
    assert.doesNotMatch(agentMapper, /adapter: "native"/);
    assert.doesNotMatch(agentMapper, /version: "latest"/);
    assert.doesNotMatch(agentMapper, /versionCount: 0/);
    assert.doesNotMatch(agentMapper, /deploymentCount: 0/);
    assert.match(client, /client\.listAgentVersions\(agent\.id\)/);
    assert.match(client, /client\.listDeployments\(\)/);
    assert.doesNotMatch(generatedClient, /package_uri\?: string/);
    assert.match(agentsPage, /openCreateAgentDrawer/);
    assert.match(agentsPage, /agentForm/);
    assert.match(agentsPage, /v-model="agentForm\.name"/);
    assert.match(agentsPage, /@submit\.prevent="createAgent"/);
    assert.match(agentsPage, /openArchiveAgentConfirm/);
    assert.match(agentsPage, /runConfirmedArchiveAgent/);
    assert.match(agentsPage, /DangerConfirmDialog/);
    assert.match(agentsPage, /class="agent-row"/);
    assert.match(agentsPage, /class="agent-summary"/);
    assert.match(agentsPage, /class="child-workspace"/);
    assert.match(agentsPage, /activeDetailTab/);
    assert.match(agentsPage, /showVersionForm/);
    assert.match(agentsPage, /showEditVersion/);
    assert.match(agentsPage, /toggleAgentStatus/);
    assert.match(agentsPage, /toggleVersionStatus/);
    assert.match(agentsPage, /t\("enable"\)/);
    assert.match(agentsPage, /t\("disable"\)/);
    assert.doesNotMatch(agentsPage, /@click="createAgent"/);
    assert.doesNotMatch(agentsPage, /@click="archiveAgent\(agent\.id\)"/);
    assert.doesNotMatch(agentsPage, /console-agent-\$\{agents\.value\.length \+ 1\}/);
    assert.doesNotMatch(agentsPage, /package_uri: "file:\/\/\."/);
    assert.doesNotMatch(agentsPage, /agent\.framework/);
    assert.doesNotMatch(agentsPage, /agent\.adapter/);
    assert.doesNotMatch(agentsPage, /agent\.version\b/);
    assert.doesNotMatch(agentsPage, /agent\.capabilities/);
});

test("exposes enable and disable controls for configurable runtime resources only", () => {
    const agentsPage = read("src/pages/agents/AgentsPage.vue");
    const publishedPage = read("src/pages/published/PublishedSurfacesPage.vue");
    const deploymentsPage = read("src/pages/deployments/DeploymentsPage.vue");
    const tasksPage = read("src/pages/tasks/TasksPage.vue");
    const eventsPage = read("src/pages/events/EventsPage.vue");

    assert.match(agentsPage, /toggleAgentStatus/);
    assert.match(agentsPage, /toggleVersionStatus/);
    assert.match(publishedPage, /toggleStatus/);
    assert.match(publishedPage, /selectedSurface\.value\.status !== "disabled"/);
    assert.doesNotMatch(deploymentsPage, /toggle.*Status/);
    assert.doesNotMatch(tasksPage, /toggle.*Status/);
    assert.doesNotMatch(eventsPage, /toggle.*Status/);
});

test("explains AgentVersion fields with inline user guidance", () => {
    const agentsPage = read("src/pages/agents/AgentsPage.vue");
    const messages = read("src/i18n/messages.ts");

    [
      "agentVersionFormHelp",
      "versionFieldHelp",
      "packageUriFieldHelp",
      "frameworkFieldHelp",
      "adapterFieldHelp",
      "entrypointFieldHelp",
    ].forEach((key) => {
      assert.match(agentsPage, new RegExp(`t\\(['"]${key}['"]\\)`));
      assert.match(messages, new RegExp(`${key}:`));
    });
    assert.match(agentsPage, /field-help-button/);
    assert.match(agentsPage, /aria-label="t\('versionFieldHelp'\)"/);
    assert.match(agentsPage, /placeholder="0\.1\.0"/);
    assert.match(agentsPage, /placeholder="file:\/\/\/opt\/dimoorun\/agents\/support"/);
    assert.match(agentsPage, /placeholder="agent:create_agent"/);
});

test("uses supported runtime selects for AgentVersion framework and adapter", () => {
    const agentsPage = read("src/pages/agents/AgentsPage.vue");

    assert.match(agentsPage, /supportedAgentRuntimes/);
    assert.match(agentsPage, /v-for="runtime in supportedAgentRuntimes"/);
    assert.match(agentsPage, /<select v-model="versionForm\.framework"/);
    assert.match(agentsPage, /<select v-model="versionForm\.adapter"/);
    assert.match(agentsPage, /<select v-model="editVersionForm\.framework"/);
    assert.match(agentsPage, /<select v-model="editVersionForm\.adapter"/);
    assert.match(agentsPage, /framework: "langgraph", adapter: "langgraph"/);
    assert.match(agentsPage, /framework: "langchain-agent", adapter: "langchain-agent"/);
    assert.match(agentsPage, /framework: "deepagents", adapter: "deepagents"/);
    assert.doesNotMatch(agentsPage, /<input v-model="versionForm\.framework"/);
    assert.doesNotMatch(agentsPage, /<input v-model="versionForm\.adapter"/);
});

test("uses row background instead of an action-cell selected label", () => {
    const runtimePages = [
      read("src/pages/agents/AgentsPage.vue"),
      read("src/pages/deployments/DeploymentsPage.vue"),
      read("src/pages/published/PublishedSurfacesPage.vue"),
    ];

    runtimePages.forEach((page) => {
      assert.match(page, /:class="\{ selected:/);
      assert.match(page, /:data-selected=/);
      assert.match(page, /\.selected/);
      assert.match(page, /\.selected td/);
      assert.match(page, /\[data-selected="true"\] td/);
      assert.match(page, /background: var\(--color-accent-soft\) !important/);
      assert.doesNotMatch(page, /selected-pill/);
      assert.doesNotMatch(page, /t\("selected(?:Agent|Deployment|Surface)"\)/);
    });
});

test("confirms runtime destructive actions before writing", () => {
    const tasksPage = read("src/pages/tasks/TasksPage.vue");
    const runDetail = read("src/pages/runs/RunDetailPage.vue");
    const deploymentsPage = read("src/pages/deployments/DeploymentsPage.vue");

    assert.match(tasksPage, /openCancelTaskConfirm/);
    assert.match(tasksPage, /openTaskDetail/);
    assert.match(tasksPage, /runConfirmedCancelTask/);
    assert.match(tasksPage, /DangerConfirmDialog/);
    assert.doesNotMatch(tasksPage, /@click="cancelTask\(task\.id\)"/);

    assert.match(runDetail, /openRunActionConfirm/);
    assert.match(runDetail, /runConfirmedRunAction/);
    assert.match(runDetail, /DangerConfirmDialog/);
    assert.doesNotMatch(runDetail, /@click="controlRun\('cancel'\)"/);
    assert.doesNotMatch(runDetail, /@click="controlRun\('retry'\)"/);
    assert.doesNotMatch(runDetail, /@click="controlRun\('replay'\)"/);

    assert.match(deploymentsPage, /desired_status: "draft"/);
    assert.doesNotMatch(deploymentsPage, /desired_status: "active"/);
});

test("makes generic admin CRUD production-safe", () => {
    const adminPage = read("src/pages/admin/AdminCollectionPage.vue");

    assert.match(adminPage, /openDetailDrawer/);
    assert.match(adminPage, /openEditDrawer/);
    assert.match(adminPage, /editPayloadJson/);
    assert.match(adminPage, /DangerConfirmDialog/);
    assert.match(adminPage, /runConfirmedDelete/);
    assert.doesNotMatch(adminPage, /@click="deleteItem\(item\)"/);
});

test("uses shared frontend state primitives in the deployments workflow", () => {
    const deploymentsPage = read("src/pages/deployments/DeploymentsPage.vue");
    const client = read("src/api/client.ts");
    const types = read("src/api/types.ts");
    const query = read("src/api/query.ts");
    const mutations = read("src/api/mutations.ts");
    const jsonForm = read("src/forms/jsonForm.ts");
    const jsonEditor = read("src/components/JsonSchemaEditor.vue");

    assert.match(types, /ConsoleWriteOptions/);
    assert.match(types, /auditReason\?: string/);
    assert.match(client, /X-Audit-Reason/);
    assert.match(query, /createQueryResource/);
    assert.match(query, /AbortController/);
    assert.match(query, /requestVersion/);
    assert.match(mutations, /createMutationAction/);
    assert.match(mutations, /auditReason/);
    assert.match(mutations, /resource_conflict/);
    assert.match(jsonForm, /parseJsonObject/);
    assert.match(jsonForm, /line: number/);
    assert.match(jsonForm, /column: number/);
    assert.match(jsonEditor, /JsonParseFailure/);
    assert.match(deploymentsPage, /createQueryResource/);
    assert.match(deploymentsPage, /createMutationAction/);
    assert.match(deploymentsPage, /<JsonSchemaEditor/);
    assert.doesNotMatch(deploymentsPage, /<textarea v-model="editDeploymentForm\.configJson"/);
    assert.doesNotMatch(deploymentsPage, /<textarea v-model="deploymentTaskInputJson"/);
});

test("loads the Events page from real run events", () => {
    const consoleClient = read("src/api/client.ts");
    const generatedClient = read("src/api/generated/dimoorun.ts");
    const eventsPage = read("src/pages/events/EventsPage.vue");

    assert.match(eventsPage, /consoleClient\.listEvents\(\)/);
    assert.match(generatedClient, /listEvents: \(\) => request<NativeEventRead\[\]>\(options, "\/v1\/events"\)/);
    assert.match(consoleClient, /nativeClient\(\)\.listEvents\(\)/);
    assert.doesNotMatch(consoleClient, /async listEvents\(\): Promise<CursorPage<RuntimeEvent>> \{\s*return page\(\[\]\)/);
});

test("verifies live e2e reports with required step markers in order", async () => {
    const { verifyReport, requiredMarkers } = await import("../scripts/verify-live-e2e-report.mjs");

    const validLog = requiredMarkers.join("\n");
    const validResult = verifyReport(validLog);
    assert.equal(validResult.ok, true, JSON.stringify(validResult));
    assert.deepEqual(validResult.missing, []);
    assert.deepEqual(validResult.outOfOrder, []);
    assert.deepEqual(validResult.failures, []);

    const swapped = [...requiredMarkers];
    [swapped[2], swapped[3]] = [swapped[3], swapped[2]];
    const invalidResult = verifyReport(swapped.join("\n"));
    assert.equal(invalidResult.ok, false);
    assert.ok(invalidResult.outOfOrder.length > 0, JSON.stringify(invalidResult));

    const missingResult = verifyReport(requiredMarkers.slice(0, -1).join("\n"));
    assert.equal(missingResult.ok, false);
    assert.ok(missingResult.missing.length > 0);

    const failureResult = verifyReport([...requiredMarkers, "spawn EPERM"].join("\n"));
    assert.equal(failureResult.ok, false);
    assert.ok(failureResult.failures.includes("spawn EPERM"));
});

test("defines a dedicated compatibility browser workflow for hosted proof", () => {
    const packageJson = read("package.json");
    const workflow = read("../../.github/workflows/ci.yml");

    assert.match(packageJson, /"test:e2e:0i"/);
    assert.match(packageJson, /tests\/e2e\/compatibility-explorer\.spec\.ts/);
    assert.match(packageJson, /--output test-results-0i/);
    assert.match(workflow, /npm run test:e2e:0i/);
    assert.match(workflow, /PLAYWRIGHT_HTML_REPORT: playwright-report-0i/);
    assert.match(workflow, /console-playwright-0i-report/);
});

test("defines a dedicated runtime capacity browser workflow", () => {
    const packageJson = read("package.json");
    const workflow = read("../../.github/workflows/ci.yml");
    const workersPage = read("src/pages/runtime/WorkersPage.vue");
    const instancesPage = read("src/pages/runtime/AgentInstancesPage.vue");
    const capacityPage = read("src/pages/runtime/CapacityPage.vue");
    const fixture = read("tests/fixtures/api.ts");

    assert.match(packageJson, /"test:e2e:0j"/);
    assert.match(packageJson, /tests\/e2e\/runtime-capacity\.spec\.ts/);
    assert.match(packageJson, /--output test-results-0j/);
    assert.match(workflow, /npm run test:e2e:0j/);
    assert.match(workflow, /PLAYWRIGHT_HTML_REPORT: playwright-report-0j/);
    assert.match(workflow, /console-playwright-0j-report/);

    assert.match(workersPage, /consoleClient\.listRuntimeWorkers/);
    assert.match(workersPage, /consoleClient\.getRuntimeWorker/);
    assert.match(workersPage, /consoleClient\.controlRuntimeWorker/);
    assert.match(instancesPage, /consoleClient\.listRuntimeAgentInstances/);
    assert.match(instancesPage, /consoleClient\.getRuntimeAgentInstance/);
    assert.match(capacityPage, /consoleClient\.getRuntimeCapacitySummary/);

    [
      'path === "/v1/console/workers"',
      'path === "/v1/console/agent-instances"',
      'path === "/v1/console/capacity"',
      "workerActionMatch",
      "runtimeCapacitySummaryResponse",
    ].forEach((literal) => assert.match(fixture, new RegExp(literal.replaceAll("/", "\\/"))));
});

test("documents the shared phase-0l browser proof flow", () => {
    const packageJson = read("package.json");
    const readme = read("README.md");
    const workflow = read("../../.github/workflows/ci.yml");
    const sharedRunner = read("scripts/run-phase-e2e.mjs");

    assert.match(packageJson, /"test:e2e:0l": "node scripts\/verify-phase-0l-proof\.mjs"/);
    assert.match(readme, /Phase 0L Browser Proof/);
    assert.match(readme, /npm run test:e2e:0j/);
    assert.match(readme, /npm run test:e2e:0l/);
    assert.match(readme, /\.phase-e2e-proof\.json/);
    assert.match(workflow, /npm run test:e2e:0j/);
    assert.match(workflow, /npm run test:e2e:0l/);
    assert.ok(workflow.indexOf("npm run test:e2e:0j") < workflow.indexOf("npm run test:e2e:0l"));
    assert.match(sharedRunner, /rmSync\(phaseProofPath, \{ force: true \}\)/);
});

test("renders platform settings boundaries and danger impact preview", () => {
    const settingsPage = read("src/pages/settings/PlatformSettingsPage.vue");
    const dangerPage = read("src/pages/settings/DangerZonePage.vue");

    assert.match(settingsPage, /snapshot\.scope_defaults/);
    assert.match(settingsPage, /Organization defaults/);
    assert.match(settingsPage, /Project defaults/);
    assert.match(settingsPage, /Environment defaults/);
    assert.match(settingsPage, /read-only/);

    assert.match(dangerPage, /preview\.affected_resources/);
    assert.match(dangerPage, /Affected resources/);
    assert.match(dangerPage, /Confirmation phrase:/);
    assert.match(dangerPage, /result\.request_id/);
    assert.match(dangerPage, /freeze_writes/);
});

test("verifies phase-0l proof files before emitting a derived report", () => {
    const tempRoot = mkdtempSync(join(tmpdir(), "dimoorun-phase0l-proof-"));
    const reportDir = join(tempRoot, "playwright-report-0l");

    try {
        const missingProof = phase0LVerifier.runPhase0LVerifier({
            rootDir: tempRoot,
            reportName: reportDir,
        });
        assert.equal(missingProof.ok, false);
        assert.match(missingProof.message, /Missing shared phase proof/);

        writeFileSync(
            join(tempRoot, ".phase-e2e-proof.json"),
            JSON.stringify({ spec_path: "tests/e2e/runtime-capacity.spec.ts", phases: ["0j"] }),
            "utf8",
        );
        const wrongProof = phase0LVerifier.runPhase0LVerifier({
            rootDir: tempRoot,
            reportName: reportDir,
        });
        assert.equal(wrongProof.ok, false);
        assert.match(wrongProof.message, /does not include phase 0L coverage/);

        writeFileSync(
            join(tempRoot, ".phase-e2e-proof.json"),
            JSON.stringify({
                spec_path: "tests/e2e/runtime-capacity.spec.ts",
                phases: ["0j", "0l"],
                generated_at: "2026-06-11T00:00:00.000Z",
            }),
            "utf8",
        );
        const validProof = phase0LVerifier.runPhase0LVerifier({
            rootDir: tempRoot,
            reportName: reportDir,
        });
        assert.equal(validProof.ok, true, validProof.message);
        assert.match(validProof.message, /Phase 0L proof accepted from tests\/e2e\/runtime-capacity\.spec\.ts/);
        assert.equal(existsSync(join(reportDir, "index.html")), true);
        const reportHtml = readFileSync(join(reportDir, "index.html"), "utf8");
        assert.match(reportHtml, /Phase 0L Browser Proof/);
        assert.match(reportHtml, /runtime-capacity\.spec\.ts/);
    } finally {
        rmSync(tempRoot, { force: true, recursive: true });
    }
});
