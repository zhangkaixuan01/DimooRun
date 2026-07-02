<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("compatibilityKicker") }}</p>
        <h1 class="page-title">{{ t("compatibility") }}</h1>
        <p class="page-subtitle">{{ t("compatibilityCopy") }}</p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="mode !== 'offline'" class="compatibility-layout">
      <section class="panel certification-matrix" :aria-label="t('adapterCertificationMatrix')">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("adapterCertificationMatrix") }}</p>
            <h2 class="panel-title">{{ t("adapterCapabilityBoundary") }}</h2>
          </div>
        </header>
        <div class="matrix-scroll">
          <table class="matrix-table">
            <thead>
              <tr>
                <th>{{ t("adapter") }}</th>
                <th v-for="capability in certificationCapabilities" :key="capability">{{ capability }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in certificationRows" :key="row.adapter">
                <th>
                  <strong>{{ row.label }}</strong>
                  <span class="mono">{{ row.adapter }}</span>
                </th>
                <td v-for="capability in certificationCapabilities" :key="`${row.adapter}-${capability}`">
                  <span class="cert-pill" :class="`status-${row.statuses[capability].status}`">
                    {{ certificationStatusLabel(row.statuses[capability].status) }}
                  </span>
                  <small>{{ row.statuses[capability].evidence }}</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <form class="panel migration-form" @submit.prevent="runMigrationReport">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("migrationReport") }}</p>
            <h2 class="panel-title">{{ t("evaluateMigrationEffort") }}</h2>
          </div>
        </header>
        <div class="form-grid">
          <label>
            <span>{{ t("framework") }}</span>
            <input v-model="migrationForm.framework" class="input" />
          </label>
          <label>
            <span>{{ t("adapter") }}</span>
            <input v-model="migrationForm.adapter" class="input" />
          </label>
          <label>
            <span>{{ t("capabilities") }}</span>
            <input v-model="migrationForm.capabilities" class="input" placeholder="assistants,threads,runs" />
          </label>
          <label>
            <span>{{ t("streamEvents") }}</span>
            <input v-model="migrationForm.streamingModes" class="input" placeholder="events,updates" />
          </label>
          <label>
            <span>{{ t("secrets") }}</span>
            <input v-model="migrationForm.requiredSecrets" class="input" placeholder="secret://openai" />
          </label>
          <label>
            <span>{{ t("tools") }}</span>
            <input v-model="migrationForm.customTools" class="input" placeholder="pagerduty.lookup" />
          </label>
          <label class="checkbox">
            <input v-model="migrationForm.usesCheckpointing" type="checkbox" />
            <span>Checkpoint</span>
          </label>
          <label class="checkbox">
            <input v-model="migrationForm.requiresInterrupts" type="checkbox" />
            <span>Interrupt</span>
          </label>
        </div>
        <div class="action-row">
          <button class="button primary" type="submit" :disabled="busy">{{ t("generateMigrationReport") }}</button>
        </div>
      </form>

      <MigrationReportPanel :report="migrationReport" />

      <section v-if="migrationGoldenRecord" class="panel">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("migrationReport") }}</p>
            <h2 class="panel-title">{{ t("goldenCompatibilityRecord") }}</h2>
          </div>
        </header>
        <p class="mono">{{ JSON.stringify(migrationGoldenRecord, null, 2) }}</p>
      </section>

      <CompatibilityRequestBuilder
        :assistant-name="assistantName"
        :thread-label="threadLabel"
        :assistant-id="assistantId"
        :thread-id="threadId"
        :run-id="runId"
        :input-message="inputMessage"
        :busy="busy"
        @update:assistant-name="assistantName = $event"
        @update:thread-label="threadLabel = $event"
        @update:assistant-id="assistantId = $event"
        @update:thread-id="threadId = $event"
        @update:run-id="runId = $event"
        @update:input-message="inputMessage = $event"
        @create-assistant="createAssistant"
        @create-thread="createThread"
        @create-run="createRun"
        @probe-stream="probeStream"
        @join-run="joinRun"
        @cancel-run="cancelRun"
      />

      <section class="panel runtime-tools">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("explorerDrilldown") }}</p>
            <h2 class="panel-title">{{ t("lookupStatusReplay") }}</h2>
          </div>
        </header>
        <div class="builder-grid">
          <section class="workflow-panel">
            <h3>{{ t("lookupResources") }}</h3>
            <div class="action-row">
              <button class="button" type="button" :disabled="busy || !assistantId" @click="getAssistant">{{ t("getAssistant") }}</button>
              <button class="button" type="button" :disabled="busy || !threadId" @click="getThread">{{ t("getThread") }}</button>
              <button class="button" type="button" :disabled="busy || !threadId || !runId" @click="getRun">{{ t("getRun") }}</button>
            </div>
          </section>
          <section class="workflow-panel">
            <h3>{{ t("streamStatus") }}</h3>
            <div class="action-row">
              <button class="button" type="button" :disabled="busy || !threadId || !runId" @click="getStreamStatus">{{ t("loadStreamStatus") }}</button>
            </div>
            <p v-if="latestResult?.streamStatus" class="muted">
              latest_event_id: {{ latestResult.streamStatus.latest_event_id || "none" }} /
              replay_from: {{ latestResult.streamStatus.replay_from_event_id || "none" }}
            </p>
          </section>
          <form class="workflow-panel" @submit.prevent="replayEvents">
            <h3>{{ t("replayFromLastEventId") }}</h3>
            <label>
              <span>Last-Event-ID</span>
              <input v-model="lastEventId" class="input" placeholder="3102:1" />
            </label>
            <button class="button primary" type="submit" :disabled="busy || !threadId || !runId || !lastEventId">
              {{ t("replayEvents") }}
            </button>
          </form>
        </div>
      </section>

      <section class="panel explorer-results">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("explorerResults") }}</p>
            <h2 class="panel-title">{{ t("runtimeConfidence") }}</h2>
          </div>
        </header>

        <div v-if="assistants.length > 0" class="result-block">
          <h3>{{ t("assistants") }}</h3>
          <div class="pill-row">
            <button
              v-for="item in assistants"
              :key="String(item.compatResponse.assistant_id || item.operation)"
              class="button"
              type="button"
              @click="selectAssistant(item)"
            >
              {{ String(item.compatResponse.name || item.compatResponse.assistant_id || item.operation) }}
            </button>
          </div>
        </div>

        <div v-if="latestResult" class="result-block">
          <h3>{{ latestResult.operation }}</h3>
          <p class="mono">{{ JSON.stringify(latestResult.compatResponse, null, 2) }}</p>
          <div class="link-list">
            <ResourceLink v-for="link in latestResult.resourceLinks" :key="`${link.label}-${link.path}`" :to="link.path">
              {{ link.label }}
            </ResourceLink>
          </div>
          <p v-if="latestResult.divergenceReason" class="danger-text">
            divergence: {{ latestResult.divergenceReason }}
          </p>
        </div>

        <div v-if="latestResult?.goldenRecord" class="result-block">
          <h3>{{ t("goldenCompatibilityRecord") }}</h3>
          <p class="mono">{{ JSON.stringify(latestResult.goldenRecord, null, 2) }}</p>
        </div>

        <div v-if="latestResult?.unsupportedCapabilityExplanations.length" class="result-block">
          <h3>{{ t("unsupportedCapabilityExplanation") }}</h3>
          <ul class="stream-list">
            <li
              v-for="item in latestResult.unsupportedCapabilityExplanations"
              :key="String(item.capability)"
            >
              {{ item.capability }}: {{ item.reason }}
            </li>
          </ul>
        </div>

        <div v-if="latestResult?.streamEvents?.length" class="result-block">
          <h3>{{ t("streamEvents") }}</h3>
          <ul class="stream-list">
            <li v-for="event in latestResult.streamEvents" :key="String(event.event_id)">
              {{ event.type }} ({{ event.event_id }})
            </li>
          </ul>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import { apiMode, consoleClient, toConsoleApiError, type ApiMode } from "../../api/client";
import type { CompatibilityExplorerResult, CompatibilityMigrationReport } from "../../api/types";
import { useI18n } from "../../i18n/useI18n";
import CompatibilityRequestBuilder from "./CompatibilityRequestBuilder.vue";
import MigrationReportPanel from "./MigrationReportPanel.vue";

const { t } = useI18n();
const mode = apiMode() as ApiMode;
const loading = ref(false);
const busy = ref(false);
const error = ref<ReturnType<typeof toConsoleApiError> | null>(null);
const assistants = ref<CompatibilityExplorerResult[]>([]);
const latestResult = ref<CompatibilityExplorerResult | null>(null);
const migrationReport = ref<CompatibilityMigrationReport | null>(null);
const migrationGoldenRecord = ref<Record<string, unknown> | null>(null);

const assistantName = ref("support-agent");
const threadLabel = ref("migration-check");
const assistantId = ref("");
const threadId = ref("");
const runId = ref("");
const lastEventId = ref("");
const inputMessage = ref("hello from compatibility explorer");

const certificationCapabilities = [
  "invoke",
  "stream",
  "resume",
  "checkpoint",
  "interrupt",
  "cancel",
  "idempotency",
  "error mapping",
] as const;
type CertificationCapability = typeof certificationCapabilities[number];
type CertificationStatus = "certified" | "limited" | "unsupported" | "not-exercised";
type CertificationCell = { status: CertificationStatus; evidence: string };
const certificationRows: Array<{
  label: string;
  adapter: string;
  statuses: Record<CertificationCapability, CertificationCell>;
}> = [
  {
    label: "LangGraph",
    adapter: "langgraph",
    statuses: {
      invoke: { status: "certified", evidence: "real framework smoke" },
      stream: { status: "certified", evidence: "stream probe" },
      resume: { status: "limited", evidence: "thread resume only" },
      checkpoint: { status: "certified", evidence: "checkpoint contract" },
      interrupt: { status: "limited", evidence: "HITL mapped" },
      cancel: { status: "certified", evidence: "run cancel" },
      idempotency: { status: "certified", evidence: "native task key" },
      "error mapping": { status: "certified", evidence: "normalized errors" },
    },
  },
  {
    label: "LangChain Agent",
    adapter: "langchain-agent",
    statuses: {
      invoke: { status: "certified", evidence: "real framework smoke" },
      stream: { status: "limited", evidence: "token/event bridge" },
      resume: { status: "unsupported", evidence: "no native checkpoint" },
      checkpoint: { status: "limited", evidence: "external store required" },
      interrupt: { status: "limited", evidence: "middleware mapped" },
      cancel: { status: "certified", evidence: "run cancel" },
      idempotency: { status: "certified", evidence: "native task key" },
      "error mapping": { status: "certified", evidence: "normalized errors" },
    },
  },
  {
    label: "DeepAgents",
    adapter: "deepagents",
    statuses: {
      invoke: { status: "certified", evidence: "real framework smoke" },
      stream: { status: "limited", evidence: "events only" },
      resume: { status: "limited", evidence: "backend dependent" },
      checkpoint: { status: "limited", evidence: "state backend" },
      interrupt: { status: "limited", evidence: "approval bridge" },
      cancel: { status: "not-exercised", evidence: "contract pending" },
      idempotency: { status: "certified", evidence: "native task key" },
      "error mapping": { status: "certified", evidence: "normalized errors" },
    },
  },
];

const migrationForm = ref({
  framework: "langgraph",
  adapter: "langgraph",
  capabilities: "assistants,threads,runs,stream",
  streamingModes: "events,updates",
  requiredSecrets: "secret://openai",
  customTools: "",
  usesCheckpointing: true,
  requiresInterrupts: false,
});

const capabilityList = computed(() => splitCsv(migrationForm.value.capabilities));
const streamingModeList = computed(() => splitCsv(migrationForm.value.streamingModes));
const requiredSecretList = computed(() => splitCsv(migrationForm.value.requiredSecrets));
const customToolList = computed(() => splitCsv(migrationForm.value.customTools));

function syncQuery() {
  const url = new URL(window.location.href);
  setQueryParam(url, "assistant_id", assistantId.value);
  setQueryParam(url, "thread_id", threadId.value);
  setQueryParam(url, "run_id", runId.value);
  setQueryParam(url, "last_event_id", lastEventId.value);
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
}

async function loadAssistants() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    assistants.value = (await consoleClient.listCompatibilityAssistants()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function runMigrationReport() {
  busy.value = true;
  error.value = null;
  try {
    const response = await consoleClient.createCompatibilityMigrationReport({
      framework: migrationForm.value.framework,
      adapter: migrationForm.value.adapter,
      capabilities: capabilityList.value,
      streaming_modes: streamingModeList.value,
      required_secrets: requiredSecretList.value,
      custom_tools: customToolList.value,
      uses_checkpointing: migrationForm.value.usesCheckpointing,
      requires_interrupts: migrationForm.value.requiresInterrupts,
    });
    migrationReport.value = response.report;
    migrationGoldenRecord.value = response.goldenRecord;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function createAssistant() {
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.createCompatibilityAssistant({
      name: assistantName.value,
      metadata: { source: "console-explorer" },
    });
    assistantId.value = String(latestResult.value.compatResponse.assistant_id || "");
    assistants.value = [latestResult.value, ...assistants.value.filter(
      (item) => item.compatResponse.assistant_id !== latestResult.value?.compatResponse.assistant_id,
    )];
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function createThread() {
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.createCompatibilityThread({
      metadata: { label: threadLabel.value },
    });
    threadId.value = String(latestResult.value.compatResponse.thread_id || "");
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function createRun() {
  if (!assistantId.value || !threadId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.createCompatibilityRun(threadId.value, {
      assistant_id: assistantId.value,
      input: { message: inputMessage.value },
    });
    runId.value = String(latestResult.value.compatResponse.run_id || "");
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function probeStream() {
  if (!assistantId.value || !threadId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.probeCompatibilityStream(threadId.value, {
      assistant_id: assistantId.value,
      input: { message: inputMessage.value },
    });
    runId.value = String(latestResult.value.compatResponse.run_id || runId.value);
    lastEventId.value = String(latestResult.value.streamStatus?.replay_from_event_id || `${runId.value}:1`);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function joinRun() {
  if (!threadId.value || !runId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.joinCompatibilityRun(threadId.value, Number(runId.value));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function cancelRun() {
  if (!threadId.value || !runId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.cancelCompatibilityRun(threadId.value, Number(runId.value));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function getAssistant() {
  if (!assistantId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.getCompatibilityAssistant(assistantId.value);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function getThread() {
  if (!threadId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.getCompatibilityThread(threadId.value);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function getRun() {
  if (!threadId.value || !runId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.getCompatibilityRun(threadId.value, Number(runId.value));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function getStreamStatus() {
  if (!threadId.value || !runId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.getCompatibilityStreamStatus(
      threadId.value,
      Number(runId.value),
    );
    lastEventId.value = String(
      latestResult.value.streamStatus?.replay_from_event_id
        || latestResult.value.streamStatus?.latest_event_id
        || lastEventId.value,
    );
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function replayEvents() {
  if (!threadId.value || !runId.value || !lastEventId.value) return;
  busy.value = true;
  error.value = null;
  try {
    latestResult.value = await consoleClient.replayCompatibilityEvents(
      threadId.value,
      Number(runId.value),
      lastEventId.value,
    );
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function selectAssistant(item: CompatibilityExplorerResult) {
  assistantId.value = String(item.compatResponse.assistant_id || "");
  latestResult.value = item;
}

function splitCsv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function setQueryParam(url: URL, key: string, value: string) {
  if (value) {
    url.searchParams.set(key, value);
    return;
  }
  url.searchParams.delete(key);
}

function certificationStatusLabel(status: CertificationStatus): string {
  if (status === "certified") return t("certified");
  if (status === "limited") return t("limited");
  if (status === "unsupported") return t("unsupported");
  return t("notExercised");
}

watch([assistantId, threadId, runId, lastEventId], syncQuery);

onMounted(async () => {
  const params = new URLSearchParams(window.location.search);
  assistantId.value = params.get("assistant_id") || "";
  threadId.value = params.get("thread_id") || "";
  runId.value = params.get("run_id") || "";
  lastEventId.value = params.get("last_event_id") || "";
  await loadAssistants();
});
</script>

<style scoped>
.compatibility-layout {
  display: grid;
  gap: 16px;
}

.migration-form,
.explorer-results,
.certification-matrix {
  display: grid;
  gap: 14px;
}

.matrix-scroll {
  overflow-x: auto;
}

.matrix-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.matrix-table th,
.matrix-table td {
  border-bottom: 1px solid var(--color-border);
  padding: 10px;
  text-align: left;
  vertical-align: top;
}

.matrix-table th:first-child {
  width: 180px;
}

.matrix-table th span {
  display: block;
  margin-top: 4px;
}

.cert-pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 0.72rem;
  font-weight: 800;
  text-transform: uppercase;
}

.cert-pill.status-certified {
  background: color-mix(in srgb, var(--color-success) 16%, transparent);
  color: var(--color-success);
}

.cert-pill.status-limited,
.cert-pill.status-not-exercised {
  background: color-mix(in srgb, var(--color-warning) 18%, transparent);
  color: var(--color-warning);
}

.cert-pill.status-unsupported {
  background: color-mix(in srgb, var(--color-danger) 14%, transparent);
  color: var(--color-danger);
}

.matrix-table small {
  display: block;
  margin-top: 5px;
  color: var(--color-text-muted);
}

.section-kicker {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  margin: 0 0 4px;
  text-transform: uppercase;
}

.form-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.checkbox {
  align-content: center;
  grid-template-columns: auto 1fr;
}

.checkbox input {
  margin: 0;
}

label {
  display: grid;
  gap: 6px;
}

label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 600;
}

.action-row,
.pill-row,
.link-list,
.builder-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.builder-grid {
  align-items: stretch;
}

.runtime-tools {
  display: grid;
  gap: 14px;
}

.workflow-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  background: var(--color-surface-muted);
  min-width: min(260px, 100%);
}

.result-block {
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
}

.result-block h3 {
  margin: 0;
  font-size: 1rem;
}

.mono {
  margin: 0;
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: 12px;
}

.stream-list {
  margin: 0;
  padding-left: 18px;
}
</style>
