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

    <div class="table-wrap">
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
import { computed, ref } from "vue";

import { runs } from "../../api/mockData";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const query = ref("");
const status = ref("");

const filteredRuns = computed(() =>
  runs.filter((run) => {
    const matchesQuery = `${run.id} ${run.agent}`.toLowerCase().includes(query.value.toLowerCase());
    const matchesStatus = status.value ? run.status === status.value : true;
    return matchesQuery && matchesStatus;
  }),
);
</script>
