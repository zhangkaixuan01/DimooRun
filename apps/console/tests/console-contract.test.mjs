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
