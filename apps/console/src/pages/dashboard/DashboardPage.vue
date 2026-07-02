<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runtimeControlPlane") }}</p>
        <h1 class="page-title">{{ t("dashboard") }}</h1>
        <p class="page-subtitle">
          {{ t("dashboardCopy") }}
        </p>
      </div>
      <TimeRangePicker />
    </header>

    <div class="overview-strip">
      <MetricCard :label="t('todayRuns')" :value="formatNumber(summary.runCountToday)" :delta="modeLabel" tone="neutral" />
      <MetricCard :label="t('successRate')" :value="formatPercent(summary.successRate)" :delta="modeLabel" tone="neutral" />
      <MetricCard :label="t('p95Latency')" :value="formatLatency(summary.p95LatencyMs)" :delta="t('noTrendData')" tone="neutral" />
      <MetricCard :label="t('monthlyCost')" :value="formatCurrency(summary.monthlyCostUsd)" :delta="t('noCostData')" tone="neutral" />
    </div>

    <section class="panel command-center">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("firstRunCommandCenter") }}</h2>
          <p class="panel-copy">{{ t("firstRunCommandCenterCopy") }}</p>
        </div>
        <RouterLink class="command-center-link" to="/runs">{{ t("inspectRunEvidence") }}</RouterLink>
      </div>
      <div class="next-actions-grid">
        <RouterLink
          v-for="action in nextActions"
          :key="action.label"
          class="next-action-card"
          :to="action.to"
        >
          <span class="next-action-step">{{ action.step }}</span>
          <strong>{{ action.label }}</strong>
          <span>{{ action.copy }}</span>
          <code>{{ action.command }}</code>
        </RouterLink>
      </div>
    </section>

    <div class="workbench-grid">
      <div class="workbench-main">
        <section class="panel trend-panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">{{ t("runVolumeSuccessRate") }}</h2>
              <p class="panel-copy">{{ t("dashboardTrendCopy") }}</p>
            </div>
            <StatusBadge :status="mode === 'live' ? 'running' : mode" :label="modeLabel" />
          </div>
          <div v-if="trendPoints.length > 0" class="panel-body"><RuntimeTrendChart :trend-points="trendPoints" /></div>
          <div v-else class="panel-body empty-panel">{{ t("noTrendData") }}</div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">{{ t("recentFailures") }}</h2>
              <p class="panel-copy">{{ t("recentFailuresCopy") }}</p>
            </div>
          </div>
          <div class="panel-body compact-list">
            <p v-for="run in failedRuns" :key="run.runId">
              <ResourceLink :to="`/runs/${run.runId}`">{{ run.runId }}</ResourceLink>
              <span>{{ run.errorSummary }}</span>
            </p>
            <p v-if="failedRuns.length === 0" class="muted">{{ t("emptyState") }}</p>
          </div>
        </section>
      </div>

      <aside class="workbench-side">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">{{ t("workerHealth") }}</h2>
              <p class="panel-copy">{{ t("workerHealthCopy") }}</p>
            </div>
            <StatusBadge :status="summary.workerReady === summary.workerTotal ? 'ready' : 'degraded'" :label="`${summary.workerReady} / ${summary.workerTotal} ready`" />
          </div>
          <div class="panel-body health-grid">
            <div><strong>{{ summary.queueBacklog }}</strong><span>{{ t("queueBacklog") }}</span></div>
            <div><strong>{{ summary.runningRuns }}</strong><span>{{ t("runningRuns") }}</span></div>
            <div><strong>{{ summary.workerTotal }}</strong><span>{{ t("agentInstances") }}</span></div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header"><h2 class="panel-title">{{ t("activeAlerts") }}</h2></div>
          <div class="panel-body compact-list">
            <p v-for="failure in failedRuns" :key="failure.runId">
              <StatusBadge :status="failure.status" :label="failure.status" />
              <span>{{ failure.errorSummary }}</span>
            </p>
            <p v-if="failedRuns.length === 0" class="muted">{{ t("emptyState") }}</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header"><h2 class="panel-title">{{ t("pendingApprovals") }}</h2></div>
          <div class="panel-body compact-list">
            <p v-for="action in pendingActions" :key="`${action.action}-${action.resourceId}`">
              <ResourceLink to="/deployments">{{ action.resourceId }}</ResourceLink>
              <span>{{ action.action }}</span>
              <small v-if="action.disabledReason">{{ action.disabledReason }}</small>
            </p>
            <p v-if="pendingActions.length === 0" class="muted">{{ t("emptyState") }}</p>
          </div>
        </section>
      </aside>
    </div>
    <ApiState :mode="mode" :loading="loading" :error="error" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import MetricCard from "../../components/MetricCard.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import RuntimeTrendChart from "../../components/RuntimeTrendChart.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import TimeRangePicker from "../../components/TimeRangePicker.vue";
import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { ConsolePendingAction, ConsoleRecentFailure, DashboardSummary } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const summary = ref<DashboardSummary>({
  runCountToday: 0,
  successRate: 0,
  p95LatencyMs: 0,
  p99LatencyMs: 0,
  queueBacklog: 0,
  workerReady: 0,
  workerTotal: 0,
  monthlyCostUsd: 0,
  pendingApprovals: 0,
  runningRuns: 0,
  activeIncidents: 0,
});
const failedRuns = ref<ConsoleRecentFailure[]>([]);
const pendingActions = ref<ConsolePendingAction[]>([]);
const modeLabel = computed(() => (mode === "live" ? t("live") : t("offline")));
const trendPoints = ref<Array<{ label: string; runs: number; successRate: number }>>([]);
const nextActions = computed(() => [
  {
    step: "01",
    label: t("publishExistingAgent"),
    copy: t("publishExistingAgentCopy"),
    command: "dimoorun publish examples/langgraph/support-agent",
    to: "/packages",
  },
  {
    step: "02",
    label: t("deployAgentVersion"),
    copy: t("deployAgentVersionCopy"),
    command: "dimoorun deploy support-agent --env local",
    to: "/deployments",
  },
  {
    step: "03",
    label: t("runAgentTask"),
    copy: t("runAgentTaskCopy"),
    command: "dimoorun run support-agent --env local --watch",
    to: "/tasks",
  },
  {
    step: "04",
    label: t("inspectRunEvidence"),
    copy: t("inspectRunEvidenceCopy"),
    command: "dimoorun open --run-id <RUN_ID>",
    to: "/runs",
  },
]);

async function loadDashboard() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [overview, metrics] = await Promise.all([
      consoleClient.getRuntimeOverview(),
      consoleClient.getRuntimeMetricsSummary(),
    ]);
    summary.value = {
      ...overview.summary,
      ...metrics.summary,
    };
    trendPoints.value = metrics.trendPoints;
    failedRuns.value = overview.recentFailures;
    pendingActions.value = overview.pendingActions;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function formatPercent(value: number): string {
  return value ? `${(value * 100).toFixed(1)}%` : "0%";
}

function formatLatency(value: number): string {
  return value ? `${(value / 1000).toFixed(2)}s` : "n/a";
}

function formatCurrency(value: number): string {
  return value ? `$${value.toFixed(2)}` : "$0.00";
}

onMounted(loadDashboard);
</script>

<style scoped>
.health-grid {
  display: grid;
  gap: 8px;
}

.command-center {
  margin-bottom: 18px;
}

.command-center-link {
  color: var(--color-accent);
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
}

.next-actions-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.next-action-card {
  display: grid;
  min-width: 0;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--color-surface-raised) 82%, var(--color-surface-muted));
  color: inherit;
  padding: 14px;
  text-decoration: none;
  transition: border-color 180ms ease, background 180ms ease;
}

.next-action-card:hover,
.next-action-card:focus-visible {
  border-color: var(--color-accent);
  background: var(--color-surface-raised);
  outline: none;
}

.next-action-card strong {
  font-size: 15px;
}

.next-action-card span {
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.45;
}

.next-action-card code {
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  color: var(--color-text);
  font-size: 12px;
  padding: 8px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.next-action-step {
  color: var(--color-accent) !important;
  font-size: 12px !important;
  font-weight: 750;
  letter-spacing: 0.08em;
}

.health-grid div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-raised) 78%, var(--color-surface-muted));
  padding: 10px 12px;
}

.health-grid strong {
  font-size: 22px;
  font-weight: 650;
}

.health-grid span,
.compact-list span {
  color: var(--color-text-muted);
}

.compact-list {
  display: grid;
  gap: 12px;
}

.compact-list p {
  display: grid;
  grid-template-columns: minmax(100px, 0.7fr) minmax(0, 1.3fr);
  min-width: 0;
  align-items: center;
  gap: 10px;
  margin: 0;
}

.compact-list small {
  grid-column: 2;
  color: var(--color-text-muted);
}

.empty-panel {
  color: var(--color-text-muted);
}

@media (max-width: 1024px) {
  .next-actions-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .next-actions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
