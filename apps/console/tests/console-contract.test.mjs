import { readFileSync, existsSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import assert from "node:assert/strict";

const root = fileURLToPath(new URL("..", import.meta.url));

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
