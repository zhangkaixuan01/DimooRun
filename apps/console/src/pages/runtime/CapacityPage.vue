<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime Operations</p>
        <h1 class="page-title">Capacity</h1>
        <p class="page-subtitle">
          Queue pressure, time-to-drain, saturation, and recommended operator action.
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="mode !== 'offline' && !loading && summary" class="grid cols-4">
      <MetricCard label="Queue backlog" :value="String(summary.queueBacklog)" :delta="summary.recommendedAction" tone="neutral" />
      <MetricCard label="Active attempts" :value="String(summary.activeAttempts)" :delta="`${summary.totalCapacity} capacity`" tone="neutral" />
      <MetricCard label="Saturation" :value="formatPercent(summary.saturationRatio)" :delta="`${summary.timeToDrainSeconds}s to drain`" :tone="summary.saturationRatio >= 1 ? 'bad' : summary.saturationRatio >= 0.8 ? 'warn' : 'good'" />
      <MetricCard label="Dead letters" :value="String(summary.deadLetterPressure)" :delta="`${summary.retryPressure} retrying`" :tone="summary.deadLetterPressure > 0 ? 'bad' : 'good'" />
    </div>

    <div v-if="summary" class="grid cols-2 capacity-sections">
      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">Recommended action</h2>
        </div>
        <div class="panel-body recommendation">
          <StatusBadge
            :status="summary.recommendedAction === 'steady_state' ? 'ready' : 'degraded'"
            :label="summary.recommendedAction"
          />
          <p>{{ summary.recommendedReason }}</p>
          <div class="quick-links">
            <ResourceLink to="/runtime/workers">Open workers</ResourceLink>
            <ResourceLink to="/runtime/agent-instances">Open agent instances</ResourceLink>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">Worker pressure</h2>
        </div>
        <div class="panel-body pressure-grid">
          <div>
            <strong>{{ summary.activeWorkers }}</strong>
            <span>active</span>
          </div>
          <div>
            <strong>{{ summary.drainingWorkers }}</strong>
            <span>draining</span>
          </div>
          <div>
            <strong>{{ summary.quarantinedWorkers }}</strong>
            <span>quarantined</span>
          </div>
          <div>
            <strong>{{ summary.criticalAttempts }}</strong>
            <span>critical attempts</span>
          </div>
        </div>
      </section>
    </div>

    <section v-if="summary" class="panel queue-panel">
      <div class="panel-header">
        <h2 class="panel-title">Queue drilldown</h2>
      </div>
      <div class="panel-body table-wrap">
        <table>
          <thead>
            <tr>
              <th>Queue</th>
              <th>Backlog</th>
              <th>Leased</th>
              <th>Running</th>
              <th>Retrying</th>
              <th>Dead letters</th>
              <th>Oldest age</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="queue in summary.queues" :key="queue.queue">
              <td>{{ queue.queue }}</td>
              <td>{{ queue.queueBacklog }}</td>
              <td>{{ queue.leased }}</td>
              <td>{{ queue.running }}</td>
              <td>{{ queue.retrying }}</td>
              <td>{{ queue.deadLetter }}</td>
              <td>{{ formatAge(queue.oldestTaskAgeSeconds) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
} from "../../api/client";
import type { RuntimeCapacitySummary } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import MetricCard from "../../components/MetricCard.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const summary = ref<RuntimeCapacitySummary | null>(null);

async function loadSummary() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    summary.value = await consoleClient.getRuntimeCapacitySummary();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

function formatAge(value: number | null): string {
  if (value === null) return "n/a";
  return `${Math.round(value)}s`;
}

onMounted(loadSummary);
</script>

<style scoped>
.capacity-sections,
.recommendation,
.quick-links,
.queue-panel,
.pressure-grid {
  margin-top: 16px;
}

.recommendation {
  display: grid;
  gap: 12px;
}

.quick-links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.pressure-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.pressure-grid div {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 12px;
}

.pressure-grid strong {
  display: block;
  font-size: 1.5rem;
}

.pressure-grid span {
  color: var(--color-text-muted);
}
</style>
