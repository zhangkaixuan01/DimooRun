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
          <p><strong>{{ t("deployment") }}</strong><br /><span class="mono">{{ currentRun?.deployment }}</span></p>
          <p><strong>{{ t("trace") }}</strong><br /><span class="mono">{{ currentRun?.traceId }}</span></p>
          <p><strong>{{ t("createdAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.createdAt) }}</span></p>
          <p><strong>{{ t("startedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.startedAt) }}</span></p>
          <p><strong>{{ t("finishedAt") }}</strong><br /><span class="mono">{{ formatDateTime(currentRun.finishedAt) }}</span></p>
          <p><strong>{{ t("latency") }}</strong><br /><span class="mono">{{ formatLatency(currentRun.latencyMs) }}</span></p>
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

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run, RunAttempt, RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import EventTimeline from "../../components/EventTimeline.vue";
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
const currentRun = ref<Run | null>(null);
const pendingAction = ref(false);
const runAction = ref<string | null>(null);
const selectedEventId = ref<string | null>(null);
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

async function loadRun() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [run, eventPage, attemptPage] = await Promise.all([
      consoleClient.getRun(runId.value),
      consoleClient.listRunEvents(runId.value),
      consoleClient.listRunAttempts(runId.value),
    ]);
    currentRun.value = run;
    events.value = eventPage.items;
    selectedEventId.value = eventPage.items[0]?.eventId ?? null;
    attempts.value = attemptPage.items;
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

@media (max-width: 1100px) {
  .run-grid,
  .payload-grid {
    grid-template-columns: 1fr;
  }
}
</style>
