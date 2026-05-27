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

    <div class="grid cols-4">
      <MetricCard :label="t('todayRuns')" :value="formatNumber(summary.runCountToday)" :delta="modeLabel" tone="neutral" />
      <MetricCard :label="t('successRate')" :value="formatPercent(summary.successRate)" :delta="modeLabel" tone="neutral" />
      <MetricCard :label="t('p95Latency')" :value="formatLatency(summary.p95LatencyMs)" :delta="t('noTrendData')" tone="neutral" />
      <MetricCard :label="t('monthlyCost')" :value="formatCurrency(summary.monthlyCostUsd)" :delta="t('noCostData')" tone="neutral" />
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("runVolumeSuccessRate") }}</h2>
          <StatusBadge :status="mode === 'live' ? 'running' : mode" :label="modeLabel" />
        </div>
        <div v-if="mode === 'demo'" class="panel-body"><RuntimeTrendChart /></div>
        <div v-else class="panel-body empty-panel">{{ t("noTrendData") }}</div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("workerHealth") }}</h2>
          <StatusBadge :status="summary.workerReady === summary.workerTotal ? 'ready' : 'degraded'" :label="`${summary.workerReady} / ${summary.workerTotal} ready`" />
        </div>
        <div class="panel-body health-grid">
          <div><strong>{{ summary.queueBacklog }}</strong><span>{{ t("queueBacklog") }}</span></div>
          <div><strong>{{ summary.runningRuns }}</strong><span>{{ t("runningRuns") }}</span></div>
          <div><strong>{{ summary.workerTotal }}</strong><span>{{ t("agentInstances") }}</span></div>
        </div>
      </section>
    </div>

    <div class="grid cols-3">
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("recentFailures") }}</h2></div>
        <div class="panel-body compact-list">
          <p v-for="run in failedRuns" :key="run.id">
            <ResourceLink :to="`/runs/${run.id}`">{{ run.id }}</ResourceLink>
            <span>{{ run.agent }} / {{ run.trigger }}</span>
          </p>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("activeAlerts") }}</h2></div>
        <div class="panel-body compact-list">
          <p v-for="incident in incidents" :key="incident.id">
            <StatusBadge :status="String(incident.status || 'active')" :label="String(incident.status || 'active')" />
            <span>{{ incident.name || incident.id }}</span>
          </p>
          <p v-if="incidents.length === 0" class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("pendingApprovals") }}</h2></div>
        <div class="panel-body compact-list">
          <p v-for="task in humanTasks" :key="task.id">
            <ResourceLink to="/governance/human-tasks">{{ task.id }}</ResourceLink>
            <span>{{ task.source }}</span>
          </p>
        </div>
      </section>
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
import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError, type DashboardSummary } from "../../api/client";
import type { HumanTask, Run } from "../../api/types";
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
const humanTasks = ref<HumanTask[]>([]);
const failedRuns = ref<Run[]>([]);
const incidents = ref<AdminResource[]>([]);
const modeLabel = computed(() => (mode === "live" ? t("live") : mode === "demo" ? t("demo") : t("offline")));

async function loadDashboard() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [dashboardSummary, humanTasksPage, runsPage, incidentsPage] = await Promise.all([
      consoleClient.getDashboardSummary(),
      consoleClient.listHumanTasks(),
      consoleClient.listRuns(),
      consoleClient.listAdminCollection("/v1/incidents"),
    ]);
    summary.value = dashboardSummary;
    humanTasks.value = humanTasksPage.items;
    failedRuns.value = runsPage.items.filter((run) => run.status === "failed");
    incidents.value = incidentsPage.items.filter((incident) => incident.status !== "resolved");
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
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.health-grid div {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 14px;
}

.health-grid strong {
  display: block;
  font-size: 24px;
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
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0;
}

.empty-panel {
  color: var(--color-text-muted);
}
</style>
