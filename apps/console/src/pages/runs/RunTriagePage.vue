<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runTriageKicker") }}</p>
        <h1 class="page-title">{{ t("runTriageTitle") }} #{{ runId }}</h1>
        <p class="page-subtitle">{{ t("runTriageCopy") }}</p>
      </div>
      <RouterLink class="button primary" :to="`/replay/compare?source_run_id=${runId}`">{{ t("compareReplay") }}</RouterLink>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !run" />

    <section v-if="mode !== 'offline' && !loading && run" class="panel golden-path">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("goldenOperatorDemo") }}</h2>
          <p class="panel-copy">{{ t("goldenOperatorDemoCopy") }}</p>
        </div>
      </div>
      <div class="path-steps">
        <RouterLink class="path-step" :to="`/runs/${run.id}`">
          <span>01</span>
          <strong>{{ t("failureEvidence") }}</strong>
          <small>{{ t("failureEvidenceCopy") }}</small>
        </RouterLink>
        <RouterLink class="path-step" :to="`/replay/compare?source_run_id=${run.id}`">
          <span>02</span>
          <strong>{{ t("compareReplay") }}</strong>
          <small>{{ t("compareReplayCopy") }}</small>
        </RouterLink>
        <RouterLink class="path-step" :to="`/governance/human-tasks?run_id=${run.id}`">
          <span>03</span>
          <strong>{{ t("approval") }}</strong>
          <small>{{ t("approvalEvidenceCopy") }}</small>
        </RouterLink>
        <RouterLink v-if="deploymentId" class="path-step" :to="`/deployments/${deploymentId}?tab=promotion`">
          <span>04</span>
          <strong>{{ t("promotionRollback") }}</strong>
          <small>{{ t("rollbackFromRunCopy") }}</small>
        </RouterLink>
        <RouterLink class="path-step" :to="`/observability/audit-logs?run_id=${run.id}`">
          <span>05</span>
          <strong>{{ t("auditEvidence") }}</strong>
          <small>{{ t("auditExportCopy") }}</small>
        </RouterLink>
      </div>
    </section>

    <div v-if="mode !== 'offline' && !loading && run" class="triage-grid">
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("failureContext") }}</h2></div>
        <div class="panel-body evidence-list">
          <p><strong>{{ t("status") }}</strong><br /><StatusBadge :status="run.status" :label="run.status" /></p>
          <p><strong>{{ t("agentVersionDeployment") }}</strong><br /><span class="mono">{{ run.agent }}@{{ run.version }}</span></p>
          <p><strong>{{ t("deployment") }}</strong><br /><span class="mono">{{ run.deployment }}</span></p>
          <p><strong>{{ t("error") }}</strong><br /><span>{{ errorSummary }}</span></p>
          <p><strong>{{ t("latency") }}</strong><br /><span>{{ run.latencyMs ?? "-" }} ms</span></p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("timeline") }}</h2></div>
        <div class="panel-body"><EventTimeline :events="events" :selected-event-id="selectedEventId" @select="selectedEventId = $event.eventId" /></div>
      </section>

      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("auditEvidence") }}</h2></div>
        <div class="panel-body evidence-list">
          <p><strong>{{ t("trace") }}</strong><br /><span class="mono">{{ run.traceId }}</span></p>
          <p><strong>{{ t("createdAt") }}</strong><br /><span class="mono">{{ formatDateTime(run.createdAt) }}</span></p>
          <p><strong>{{ t("input") }}</strong></p>
          <pre>{{ formatJson(run.input) }}</pre>
          <p><strong>{{ t("output") }}</strong></p>
          <pre>{{ formatJson(run.output) }}</pre>
        </div>
      </section>
    </div>

    <section v-if="mode !== 'offline' && !loading && run" class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("attempts") }}</h2></div>
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
              <td class="muted" colspan="4">{{ t("noAttemptsRecorded") }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run, RunAttempt, RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import EventTimeline from "../../components/EventTimeline.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";

const props = defineProps<{ runId: string }>();
const runId = computed(() => Number(props.runId));
const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const run = ref<Run | null>(null);
const events = ref<RuntimeEvent[]>([]);
const attempts = ref<RunAttempt[]>([]);
const selectedEventId = ref<string | null>(null);
const deploymentId = computed(() => {
  const value = Number(run.value?.deployment);
  return Number.isFinite(value) && value > 0 ? value : null;
});
const errorSummary = computed(() => {
  const value = run.value?.error;
  if (!value) return "No error payload.";
  if (typeof value.message === "string") return value.message;
  return JSON.stringify(value);
});

function formatJson(value: unknown): string {
  if (value === null || value === undefined) return "-";
  return JSON.stringify(value, null, 2);
}

async function loadTriage() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [currentRun, eventPage, attemptPage] = await Promise.all([
      consoleClient.getRun(runId.value),
      consoleClient.listRunEvents(runId.value),
      consoleClient.listRunAttempts(runId.value),
    ]);
    run.value = currentRun;
    events.value = eventPage.items;
    attempts.value = attemptPage.items;
    selectedEventId.value = eventPage.items[0]?.eventId ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(loadTriage);
</script>

<style scoped>
.triage-grid {
  display: grid;
  grid-template-columns: minmax(240px, 0.8fr) minmax(360px, 1.2fr) minmax(280px, 1fr);
  gap: 14px;
}

.golden-path {
  margin-bottom: 14px;
}

.path-steps {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.path-step {
  display: grid;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: inherit;
  padding: 12px;
  text-decoration: none;
  transition: border-color 160ms ease, background-color 160ms ease;
}

.path-step:hover,
.path-step:focus-visible {
  border-color: var(--color-accent);
  background: var(--color-surface-muted);
}

.path-step span {
  color: var(--color-accent);
  font-weight: 800;
}

.path-step small {
  color: var(--color-text-muted);
}

.evidence-list {
  display: grid;
  gap: 12px;
}

.evidence-list p {
  margin: 0;
}

pre {
  overflow: auto;
  max-height: 260px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
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

@media (max-width: 1100px) {
  .triage-grid,
  .path-steps {
    grid-template-columns: 1fr;
  }
}
</style>
