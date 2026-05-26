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
      <MetricCard :label="t('todayRuns')" value="12,840" delta="+8.2%" tone="good" />
      <MetricCard :label="t('successRate')" value="98.7%" delta="-0.4%" tone="warn" />
      <MetricCard :label="t('p95Latency')" value="2.1s" delta="-180ms" tone="good" />
      <MetricCard :label="t('monthlyCost')" value="$4,291" delta="+3.1%" tone="neutral" />
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("runVolumeSuccessRate") }}</h2>
          <StatusBadge status="running" label="live" />
        </div>
        <div class="panel-body"><RuntimeTrendChart /></div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("workerHealth") }}</h2>
          <StatusBadge status="ready" label="6 / 7 ready" />
        </div>
        <div class="panel-body health-grid">
          <div><strong>24</strong><span>{{ t("queueBacklog") }}</span></div>
          <div><strong>18</strong><span>{{ t("runningRuns") }}</span></div>
          <div><strong>9</strong><span>{{ t("agentInstances") }}</span></div>
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
          <p><StatusBadge status="degraded" label="degraded" /> {{ t("heartbeatLagAlert") }}</p>
          <p><StatusBadge status="dead_letter" label="dead letter" /> {{ t("policyQueueAlert") }}</p>
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
  </section>
</template>

<script setup lang="ts">
import MetricCard from "../../components/MetricCard.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import RuntimeTrendChart from "../../components/RuntimeTrendChart.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import TimeRangePicker from "../../components/TimeRangePicker.vue";
import { consoleClient } from "../../api/client";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const humanTasks = consoleClient.listHumanTasks().items;
const runs = consoleClient.listRuns().items;
const failedRuns = runs.filter((run) => run.status === "failed");
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
</style>
