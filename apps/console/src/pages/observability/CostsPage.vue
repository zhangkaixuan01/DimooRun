<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("observability") }}</p>
        <h1 class="page-title">{{ t("cost") }}</h1>
        <p class="page-subtitle">Track spend, token usage, and regressions by runtime scope.</p>
      </div>
      <button class="button" type="button" :disabled="loading" @click="load">
        {{ loading ? t("loading") : "Refresh" }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !error && summary?.breakdown.length === 0" />

    <template v-if="mode !== 'offline' && summary">
      <div class="toolbar panel">
        <div class="toolbar-grid">
          <label>
            <span>Group by</span>
            <select v-model="groupBy" class="input" @change="load">
              <option value="deployment">Deployment</option>
              <option value="run">Run</option>
              <option value="provider">Provider</option>
              <option value="model">Model</option>
              <option value="agent">Agent</option>
            </select>
          </label>
          <label>
            <span>{{ t("timeRange") }}</span>
            <select v-model.number="windowDays" class="input" @change="load">
              <option :value="7">7d</option>
              <option :value="30">30d</option>
              <option :value="90">90d</option>
            </select>
          </label>
          <label>
            <span>View name</span>
            <input v-model="viewName" class="input" placeholder="provider-regressions" />
          </label>
        </div>
        <div class="toolbar-actions">
          <button class="button" type="button" :disabled="loading || !canSaveView" @click="saveCurrentView">
            Save current view
          </button>
          <button
            class="button"
            type="button"
            :disabled="loading || selectedSavedViewId === null || !canSaveView"
            @click="updateSelectedView"
          >
            Update selected
          </button>
        </div>
      </div>

      <div class="grid cols-4 metrics">
        <MetricCard label="Total cost" :value="formatUsd(summary.totalCostUsd)" :delta="`${summary.groupBy} view`" tone="neutral" />
        <MetricCard label="Total tokens" :value="formatInteger(summary.totalTokens)" :delta="`${summary.windowDays}d window`" tone="neutral" />
        <MetricCard label="Runs" :value="formatInteger(summary.runCount)" :delta="`${summary.failedRunCount} failed`" :tone="summary.failedRunCount > 0 ? 'warn' : 'good'" />
        <MetricCard label="Anomalies" :value="formatInteger(anomalies.length)" :delta="highestSeverityLabel" :tone="highestSeverityTone" />
      </div>

      <section class="panel saved-views">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Saved views</h2>
            <p class="panel-copy">Persist group-by and time-window combinations that operators return to during cost triage.</p>
          </div>
        </div>
        <div class="panel-body">
          <div v-if="savedViews.length === 0" class="muted">No saved cost views yet.</div>
          <div v-else class="saved-view-list">
            <article
              v-for="view in savedViews"
              :key="view.id"
              class="saved-view-item"
              :class="{ selected: view.id === selectedSavedViewId }"
            >
              <div class="saved-view-head">
                <strong>{{ view.name }}</strong>
                <StatusBadge :status="view.status" :label="view.status" />
              </div>
              <p class="muted">{{ view.groupBy }} · {{ view.windowDays }}d</p>
              <div class="saved-view-actions">
                <button class="button" type="button" :disabled="loading" @click="applySavedView(view.id)">
                  Apply
                </button>
                <button class="button danger" type="button" :disabled="loading" @click="deleteSavedView(view.id)">
                  {{ t("delete") }}
                </button>
              </div>
            </article>
          </div>
        </div>
      </section>

      <div class="grid cols-2 sections">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Breakdown</h2>
              <p class="panel-copy">Top contributors for the selected spend view.</p>
            </div>
          </div>
          <div class="panel-body table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Scope</th>
                  <th>{{ t("cost") }}</th>
                  <th>{{ t("promptTokens") }}/{{ t("completionTokens") }}</th>
                  <th>{{ t("runs") }}</th>
                  <th>{{ t("recentFailures") }}</th>
                  <th>Quality</th>
                  <th>Latest</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in summary.breakdown" :key="`${item.groupBy}:${item.key}`">
                  <td>
                    <strong>{{ item.label }}</strong>
                    <div class="muted mono">{{ item.key }}</div>
                  </td>
                  <td>{{ formatUsd(item.totalCostUsd) }}</td>
                  <td>{{ formatInteger(item.totalTokens) }}</td>
                  <td>{{ item.runCount }}</td>
                  <td>{{ item.failedRunCount }}</td>
                  <td>
                    <div v-if="item.qualityGate" class="quality-overlay">
                      <StatusBadge
                        :status="severityStatus(item.qualityGate.promotionAllowed ? 'low' : 'high')"
                        :label="item.qualityGate.status"
                      />
                      <span v-if="item.qualityGate.experimentRunId" class="mono muted">
                        exp #{{ item.qualityGate.experimentRunId }}
                      </span>
                      <span
                        v-if="item.qualityGate.averageScore !== null && item.qualityGate.minScore !== null"
                        class="muted"
                      >
                        {{ item.qualityGate.averageScore.toFixed(2) }}/{{ item.qualityGate.minScore.toFixed(2) }}
                      </span>
                    </div>
                    <span v-else class="muted">{{ t("none") }}</span>
                  </td>
                  <td>
                    <ResourceLink v-if="item.latestRunId" :to="`/runs/${item.latestRunId}`">
                      Run #{{ item.latestRunId }}
                    </ResourceLink>
                    <span v-else class="muted">{{ t("none") }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Anomalies</h2>
              <p class="panel-copy">Cost spikes, failed spend, and provider-linked regressions.</p>
            </div>
          </div>
          <div class="panel-body anomaly-layout">
            <div class="anomaly-list">
              <button
                v-for="item in anomalies"
                :key="`${item.kind}:${item.runId ?? item.deploymentId ?? item.provider ?? item.model}`"
                class="anomaly-item"
                :class="{ selected: selectedAnomaly?.kind === item.kind && selectedAnomaly?.runId === item.runId }"
                type="button"
                @click="selectedAnomaly = item"
              >
                <div class="anomaly-head">
                  <strong>{{ item.title }}</strong>
                  <StatusBadge :status="severityStatus(item.severity)" :label="item.severity" />
                </div>
                <p>{{ item.summary }}</p>
                <small>{{ formatUsd(item.costUsd) }}</small>
              </button>
            </div>

            <div class="anomaly-detail panel inset" v-if="selectedAnomaly">
              <div class="panel-header">
                <h3 class="panel-title">{{ selectedAnomaly.title }}</h3>
              </div>
              <div class="panel-body detail-stack">
                <p>{{ selectedAnomaly.summary }}</p>
                <p>kind: <span class="mono">{{ selectedAnomaly.kind }}</span></p>
                <p>{{ t("cost") }}: {{ formatUsd(selectedAnomaly.costUsd) }}</p>
                <p v-if="selectedAnomaly.provider">provider: {{ selectedAnomaly.provider }}</p>
                <p v-if="selectedAnomaly.model">model: {{ selectedAnomaly.model }}</p>
                <ResourceLink v-if="selectedAnomaly.runId" :to="`/runs/${selectedAnomaly.runId}`">
                  Open Run #{{ selectedAnomaly.runId }}
                </ResourceLink>
                <ResourceLink v-if="selectedAnomaly.deploymentId" :to="`/deployments/${selectedAnomaly.deploymentId}`">
                  Open Deployment #{{ selectedAnomaly.deploymentId }}
                </ResourceLink>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { CostAnomaly, CostBreakdown, CostSavedView, CostSummary } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import MetricCard from "../../components/MetricCard.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const summary = ref<CostSummary | null>(null);
const anomalies = ref<CostAnomaly[]>([]);
const selectedAnomaly = ref<CostAnomaly | null>(null);
const groupBy = ref<CostBreakdown["groupBy"]>("deployment");
const windowDays = ref(30);
const savedViews = ref<CostSavedView[]>([]);
const selectedSavedViewId = ref<number | null>(null);
const viewName = ref("default-cost-view");

const canSaveView = computed(() => viewName.value.trim().length > 0);

const highestSeverityLabel = computed(() => {
  if (anomalies.value.some((item) => item.severity === "critical")) return "critical";
  if (anomalies.value.some((item) => item.severity === "high")) return "high";
  if (anomalies.value.some((item) => item.severity === "medium")) return "medium";
  return "stable";
});

const highestSeverityTone = computed<"good" | "warn" | "bad">(() => {
  if (highestSeverityLabel.value === "critical" || highestSeverityLabel.value === "high") return "bad";
  if (highestSeverityLabel.value === "medium") return "warn";
  return "good";
});

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [nextSummary, nextAnomalies, nextSavedViews] = await Promise.all([
      consoleClient.getCostSummary(groupBy.value, windowDays.value),
      consoleClient.getCostAnomalies(windowDays.value),
      consoleClient.listCostSavedViews(),
    ]);
    summary.value = nextSummary;
    anomalies.value = nextAnomalies;
    savedViews.value = nextSavedViews.items;
    if (
      selectedSavedViewId.value !== null
      && !nextSavedViews.items.some((item) => item.id === selectedSavedViewId.value)
    ) {
      selectedSavedViewId.value = null;
    }
    selectedAnomaly.value = nextAnomalies[0] ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function severityStatus(severity: string): string {
  if (severity === "critical" || severity === "high") return "failed";
  if (severity === "medium") return "degraded";
  return "ready";
}

async function saveCurrentView() {
  if (mode === "offline" || !canSaveView.value) return;
  loading.value = true;
  error.value = null;
  try {
    const created = await consoleClient.createCostSavedView({
      name: viewName.value.trim(),
      group_by: groupBy.value,
      window_days: windowDays.value,
      filters: {},
    });
    selectedSavedViewId.value = created.id;
    await load();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function updateSelectedView() {
  if (mode === "offline" || selectedSavedViewId.value === null || !canSaveView.value) return;
  loading.value = true;
  error.value = null;
  try {
    await consoleClient.updateCostSavedView(selectedSavedViewId.value, {
      name: viewName.value.trim(),
      group_by: groupBy.value,
      window_days: windowDays.value,
      filters: {},
    });
    await load();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function applySavedView(viewId: number) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const detail = await consoleClient.getSavedCostView(viewId);
    selectedSavedViewId.value = viewId;
    viewName.value = detail.item.name;
    groupBy.value = detail.item.groupBy;
    windowDays.value = detail.item.windowDays;
    summary.value = detail.summary;
    anomalies.value = detail.anomalies;
    selectedAnomaly.value = detail.anomalies[0] ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function deleteSavedView(viewId: number) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    await consoleClient.deleteCostSavedView(viewId);
    if (selectedSavedViewId.value === viewId) {
      selectedSavedViewId.value = null;
    }
    await load();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar,
.saved-views,
.metrics,
.sections {
  margin-top: 16px;
}

.toolbar {
  padding: 16px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 220px));
  gap: 12px;
}

.toolbar-actions,
.saved-view-head,
.saved-view-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar-actions {
  margin-top: 14px;
  flex-wrap: wrap;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

label span,
.panel-copy,
.muted,
.anomaly-item p,
.anomaly-item small {
  color: var(--color-text-muted);
}

.table-wrap {
  overflow: auto;
}

.quality-overlay {
  display: grid;
  gap: 4px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  border-bottom: 1px solid var(--color-border);
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}

.anomaly-layout {
  display: grid;
  gap: 14px;
}

.saved-view-list {
  display: grid;
  gap: 10px;
}

.saved-view-item {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 12px;
}

.saved-view-item.selected {
  border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border));
  background: var(--color-accent-soft);
}

.saved-view-head {
  justify-content: space-between;
}

.anomaly-list {
  display: grid;
  gap: 10px;
}

.anomaly-item {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 12px;
  text-align: left;
}

.anomaly-item.selected {
  border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border));
  background: var(--color-accent-soft);
}

.anomaly-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.inset {
  border-style: dashed;
}

.detail-stack {
  display: grid;
  gap: 10px;
}

@media (max-width: 900px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }
}
</style>
