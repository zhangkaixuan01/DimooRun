<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runDetail") }}</p>
        <h1 class="page-title">{{ currentRun?.id ?? runId }}</h1>
        <p class="page-subtitle">{{ t("runDetailCopy") }}</p>
      </div>
      <div v-if="currentRun" class="run-actions">
        <StatusBadge :status="currentRun.status" :label="currentRun.status" />
        <button class="button danger" type="button" :disabled="pendingAction" @click="openRunActionConfirm('cancel')">{{ t("cancel") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="openRunActionConfirm('resume')">{{ t("resume") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="openRunActionConfirm('retry')">{{ t("retry") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="openRunActionConfirm('replay')">{{ t("replay") }}</button>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !currentRun" />

    <section v-if="mode !== 'offline' && !loading && !error && currentRun" class="panel action-center">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("operatorEvidencePath") }}</h2>
          <p class="panel-copy">{{ t("operatorEvidencePathCopy") }}</p>
        </div>
        <StatusBadge :status="currentRun.status" :label="currentRun.status" />
      </div>
      <div class="action-grid">
        <RouterLink class="action-card" :to="`/runs/${currentRun.id}/triage`">
          <strong>{{ t("triageRun") }}</strong>
          <span>{{ t("triageRunCopy") }}</span>
        </RouterLink>
        <RouterLink class="action-card" :to="`/replay/compare?source_run_id=${currentRun.id}`">
          <strong>{{ t("compareReplay") }}</strong>
          <span>{{ t("compareReplayCopy") }}</span>
        </RouterLink>
        <RouterLink class="action-card" :to="`/governance/human-tasks?run_id=${currentRun.id}`">
          <strong>{{ t("approval") }}</strong>
          <span>{{ t("approvalEvidenceCopy") }}</span>
        </RouterLink>
        <RouterLink v-if="deploymentId" class="action-card" :to="`/deployments/${deploymentId}?tab=promotion`">
          <strong>{{ t("rollback") }}</strong>
          <span>{{ t("rollbackFromRunCopy") }}</span>
        </RouterLink>
        <RouterLink class="action-card" :to="`/observability/audit-logs?run_id=${currentRun.id}`">
          <strong>{{ t("auditLogs") }}</strong>
          <span>{{ t("auditExportCopy") }}</span>
        </RouterLink>
      </div>
    </section>

    <section
      v-if="mode !== 'offline' && !loading && !error && currentRun"
      id="integration-evidence"
      class="panel integration-evidence"
    >
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("integrationEvidence") }}</h2>
          <p class="panel-copy">{{ t("integrationEvidenceCopy") }}</p>
        </div>
      </div>
      <div class="integration-grid">
        <section class="evidence-card">
          <h3>{{ t("traceLinks") }}</h3>
          <ul v-if="integrationEvidence.traceLinks.length > 0" class="evidence-list">
            <li v-for="link in integrationEvidence.traceLinks" :key="`${link.provider}-${link.url}`">
              <a :href="link.url" target="_blank" rel="noreferrer">{{ link.label || link.provider }}</a>
              <span class="mono">{{ link.traceId || link.status }}</span>
            </li>
          </ul>
          <p v-else class="muted">{{ t("notRecorded") }}</p>
        </section>

        <section class="evidence-card">
          <h3>{{ t("exporterStatus") }}</h3>
          <ul v-if="integrationEvidence.exporters.length > 0" class="evidence-list">
            <li v-for="exporter in integrationEvidence.exporters" :key="`${exporter.provider}-${exporter.requestId || exporter.targetRef}`">
              <strong>{{ exporter.provider }}</strong>
              <span>{{ exporter.status }}</span>
              <span class="mono">{{ exporter.exporterType || exporter.targetRef || exporter.requestId || "-" }}</span>
            </li>
          </ul>
          <p v-else class="muted">{{ t("notRecorded") }}</p>
        </section>

        <section class="evidence-card">
          <h3>{{ t("modelRoutingEvidence") }}</h3>
          <ul v-if="integrationEvidence.modelGateway.length > 0" class="evidence-list">
            <li v-for="gateway in integrationEvidence.modelGateway" :key="`${gateway.provider}-${gateway.gatewayRequestId || gateway.model}`">
              <strong>{{ gateway.provider }}</strong>
              <span class="mono">{{ gateway.gatewayName || gateway.route || gateway.gatewayRequestId || "-" }}</span>
              <span>{{ gateway.model || "-" }}</span>
              <span>{{ formatTokens(gateway.totalTokens) }} / {{ formatCost(gateway.cost, gateway.currency) }}</span>
            </li>
          </ul>
          <p v-else class="muted">{{ t("notRecorded") }}</p>
        </section>

        <section class="evidence-card">
          <h3>{{ t("failureEvidence") }}</h3>
          <ul v-if="integrationEvidence.failures.length > 0" class="evidence-list">
            <li v-for="failure in integrationEvidence.failures" :key="`${failure.provider}-${failure.errorCode || failure.message}`">
              <strong>{{ failure.provider }}</strong>
              <span>{{ failure.errorCode || failure.status }}</span>
              <span>{{ failure.message }}</span>
            </li>
          </ul>
          <p v-else class="muted">{{ t("notRecorded") }}</p>
        </section>
      </div>
    </section>

    <div v-if="mode !== 'offline' && !loading && !error && currentRun" class="run-grid">
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("eventTimeline") }}</h2></div>
        <div class="panel-body"><EventTimeline :events="events" :selected-event-id="selectedEventId" @select="selectEvent" /></div>
      </section>

      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("selectedEvent") }}</h2></div>
        <div class="panel-body detail">
          <template v-if="selectedEvent">
            <p><strong>{{ selectedEvent.type }}</strong></p>
            <p class="muted">{{ selectedEvent.summary }}</p>
            <pre>{{ formatJson(selectedEvent.payload ?? selectedEvent) }}</pre>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>

      <aside class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("metadataCost") }}</h2></div>
        <div class="panel-body">
          <p><strong>{{ t("agent") }} / {{ t("version") }}</strong><br /><span class="mono">{{ currentRun.agent }}@{{ currentRun.version }}</span></p>
          <p><strong>{{ t("deployment") }}</strong><br /><span class="mono">{{ currentRun?.deployment }}</span></p>
          <p><strong>{{ t("trace") }}</strong><br /><span class="mono">{{ currentRun?.traceId }}</span></p>
          <p><strong>{{ t("createdAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.createdAt) }}</span></p>
          <p><strong>{{ t("startedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.startedAt) }}</span></p>
          <p><strong>{{ t("finishedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.finishedAt) }}</span></p>
          <p><strong>{{ t("latency") }}</strong><br /><span class="mono">{{ formatLatency(currentRun.latencyMs) }}</span></p>
          <div class="evidence-links">
            <ResourceLink :to="`/observability/artifacts?run_id=${currentRun.id}`">{{ t("artifacts") }}</ResourceLink>
            <ResourceLink :to="`/observability/audit-logs?resource_type=run&resource_id=${currentRun.id}`">{{ t("auditLogs") }}</ResourceLink>
          </div>
          <RunCostBreakdown />
        </div>
      </aside>
    </div>

    <section v-if="mode !== 'offline' && !loading && !error && currentRun" class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("runPayloads") }}</h2></div>
      <div class="panel-body payload-grid">
        <div>
          <p class="payload-label">{{ t("input") }}</p>
          <pre>{{ formatJson(currentRun.input) }}</pre>
        </div>
        <div>
          <p class="payload-label">{{ t("output") }}</p>
          <pre>{{ formatJson(currentRun.output) }}</pre>
        </div>
        <div>
          <p class="payload-label">{{ t("error") }}</p>
          <pre>{{ formatJson(currentRun.error) }}</pre>
        </div>
      </div>
    </section>

    <section v-if="mode !== 'offline' && !loading && !error && currentRun" class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("runAttempts") }}</h2></div>
      <div class="panel-body">
        <table class="attempts-table">
          <thead>
            <tr>
              <th>{{ t("attempt") }}</th>
              <th>{{ t("worker") }}</th>
              <th>{{ t("status") }}</th>
              <th>{{ t("error") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="attempt in attempts" :key="attempt.id">
              <td class="mono">{{ attempt.attemptNo }}</td>
              <td class="mono">{{ attempt.workerId ?? "-" }}</td>
              <td><StatusBadge :status="attempt.status" :label="attempt.status" /></td>
              <td>{{ attempt.error ?? "-" }}</td>
            </tr>
            <tr v-if="attempts.length === 0">
              <td colspan="4" class="muted">{{ t("emptyState") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <DangerConfirmDialog
      :open="Boolean(runAction)"
      :title="t('confirmRunAction')"
      :message="t('confirmRunActionCopy')"
      :items="runActionConfirmItems"
      :confirm-label="runAction ? runActionLabel(runAction) : t('confirm')"
      :cancel-label="t('back')"
      :busy-label="t('saving')"
      :busy="pendingAction"
      :error="runActionError"
      @cancel="closeRunActionConfirm"
      @confirm="runConfirmedRunAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run, RunAttempt, RunIntegrationEvidence, RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import EventTimeline from "../../components/EventTimeline.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import RunCostBreakdown from "../../components/RunCostBreakdown.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";

const props = defineProps<{ runId: string }>();
const runId = computed(() => Number(props.runId));
const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const runActionError = ref<ConsoleApiError | null>(null);
const events = ref<RuntimeEvent[]>([]);
const attempts = ref<RunAttempt[]>([]);
const integrationEvidence = ref<RunIntegrationEvidence>({
  runId: runId.value,
  traceLinks: [],
  exporters: [],
  modelGateway: [],
  failures: [],
  records: [],
});
const currentRun = ref<Run | null>(null);
const pendingAction = ref(false);
const runAction = ref<string | null>(null);
const selectedEventId = ref<string | null>(null);
const deploymentId = computed(() => {
  const value = Number(currentRun.value?.deployment);
  return Number.isFinite(value) && value > 0 ? value : null;
});
const selectedEvent = computed(() => events.value.find((event) => event.eventId === selectedEventId.value) ?? events.value[0] ?? null);
const runActionConfirmItems = computed(() => currentRun.value && runAction.value ? [
  { label: t("run"), value: String(currentRun.value.id) },
  { label: t("status"), value: currentRun.value.status },
  { label: t("operations"), value: runActionLabel(runAction.value) },
] : []);

function formatJson(value: unknown): string {
  if (value === null || value === undefined) return t("noRunPayload");
  return JSON.stringify(value, null, 2);
}

function formatLatency(value: number | null): string {
  return typeof value === "number" ? `${value} ms` : "-";
}

function formatTokens(value: number | null): string {
  return typeof value === "number" ? `${value} tokens` : "-";
}

function formatCost(value: number | null, currency: string): string {
  return typeof value === "number" ? `${value.toFixed(4)} ${currency}` : "-";
}

async function loadRun() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [run, eventPage, attemptPage, evidence] = await Promise.all([
      consoleClient.getRun(runId.value),
      consoleClient.listRunEvents(runId.value),
      consoleClient.listRunAttempts(runId.value),
      consoleClient.getRunIntegrationEvidence(runId.value),
    ]);
    currentRun.value = run;
    events.value = eventPage.items;
    selectedEventId.value = eventPage.items[0]?.eventId ?? null;
    attempts.value = attemptPage.items;
    integrationEvidence.value = evidence;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function selectEvent(event: RuntimeEvent) {
  selectedEventId.value = event.eventId;
}

function openRunActionConfirm(operation: string) {
  runAction.value = operation;
  runActionError.value = null;
}

function closeRunActionConfirm() {
  if (pendingAction.value) return;
  runAction.value = null;
  runActionError.value = null;
}

function runActionLabel(operation: string): string {
  if (operation === "cancel") return t("cancel");
  if (operation === "resume") return t("resume");
  if (operation === "retry") return t("retry");
  if (operation === "replay") return t("replay");
  return operation;
}

async function runConfirmedRunAction() {
  if (!runAction.value) return;
  const operation = runAction.value;
  pendingAction.value = true;
  error.value = null;
  runActionError.value = null;
  try {
    currentRun.value = await consoleClient.controlRun(runId.value, operation);
    runAction.value = null;
  } catch (caught) {
    runActionError.value = toConsoleApiError(caught);
  } finally {
    pendingAction.value = false;
  }
}

onMounted(loadRun);
</script>

<style scoped>
.run-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(320px, 1.2fr) minmax(240px, 0.7fr);
  gap: 14px;
}

pre {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

.payload-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.payload-label {
  margin: 0 0 6px;
  font-weight: 700;
}

.attempts-table {
  width: 100%;
  border-collapse: collapse;
}

.attempts-table th,
.attempts-table td {
  border-bottom: 1px solid var(--color-border);
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}

.run-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.action-center {
  margin-bottom: 14px;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.action-card {
  display: grid;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: inherit;
  padding: 12px;
  text-decoration: none;
  transition: border-color 160ms ease, background-color 160ms ease;
}

.action-card:hover,
.action-card:focus-visible {
  border-color: var(--color-accent);
  background: var(--color-surface-muted);
}

.action-card span {
  color: var(--color-text-muted);
  font-size: 0.84rem;
}

.evidence-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}

.integration-evidence {
  margin-bottom: 14px;
}

.integration-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.evidence-card {
  display: grid;
  align-content: start;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  padding: 12px;
}

.evidence-card h3 {
  margin: 0;
  font-size: 0.94rem;
}

.evidence-list {
  display: grid;
  gap: 8px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.evidence-list li {
  display: grid;
  gap: 4px;
}

@media (max-width: 1100px) {
  .run-grid,
  .action-grid,
  .integration-grid,
  .payload-grid {
    grid-template-columns: 1fr;
  }
}
</style>
