<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runTraceCost") }}</p>
        <h1 class="page-title">{{ t("runs") }}</h1>
        <p class="page-subtitle">{{ t("runsCopy") }}</p>
      </div>
      <div class="toolbar">
        <input v-model="query" class="input" :placeholder="t('searchRunOrAgent')" />
        <select v-model="status" class="select">
          <option value="">{{ t("allStatus") }}</option>
          <option value="succeeded">{{ t("succeededStatus") }}</option>
          <option value="failed">{{ t("failedStatus") }}</option>
          <option value="running">{{ t("runningStatus") }}</option>
        </select>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && runs.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && runs.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("run") }}</th>
            <th>{{ t("agent") }}</th>
            <th>{{ t("framework") }}</th>
            <th>{{ t("actor") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("latency") }}</th>
            <th>{{ t("cost") }}</th>
            <th>{{ t("trigger") }}</th>
            <th>{{ t("trace") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in filteredRuns" :key="run.id">
            <td><ResourceLink :to="`/runs/${run.id}`">{{ run.id }}</ResourceLink></td>
            <td>{{ run.agent }}@{{ run.version }}</td>
            <td>{{ run.framework }} / {{ run.adapter }}</td>
            <td>{{ run.actor }}</td>
            <td><StatusBadge :status="run.status" :label="run.status" /></td>
            <td>{{ run.latencyMs }} ms</td>
            <td>${{ run.costUsd.toFixed(3) }}</td>
            <td>{{ run.trigger }}</td>
            <td class="mono">{{ run.traceId }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const runs = ref<Run[]>([]);
const query = ref("");
const status = ref("");

const filteredRuns = computed(() =>
  runs.value.filter((run) => {
    const matchesQuery = `${run.id} ${run.agent}`.toLowerCase().includes(query.value.toLowerCase());
    const matchesStatus = status.value ? run.status === status.value : true;
    return matchesQuery && matchesStatus;
  }),
);

async function loadRuns() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    runs.value = (await consoleClient.listRuns()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(loadRuns);
</script>
