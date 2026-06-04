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
            <th>{{ t("createdAt") }}</th>
            <th>{{ t("latency") }}</th>
            <th>{{ t("cost") }}</th>
            <th>{{ t("trigger") }}</th>
            <th>{{ t("trace") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in filteredRuns" :key="run.id">
            <td><ResourceLink :to="`/runs/${run.id}`">{{ run.id }}</ResourceLink></td>
            <td>{{ run.agent }}@{{ run.version }}</td>
            <td>{{ run.framework }} / {{ run.adapter }}</td>
            <td>{{ run.actor }}</td>
            <td><StatusBadge :status="run.status" :label="run.status" /></td>
            <td>{{ formatDateTime(run.createdAt) }}</td>
            <td>{{ formatLatency(run.latencyMs) }}</td>
            <td>{{ formatCost(run.costUsd) }}</td>
            <td>{{ run.trigger }}</td>
            <td class="mono">{{ run.traceId }}</td>
            <td class="actions-cell">
              <ResourceLink class="button" :to="`/runs/${run.id}`">{{ t("view") }}</ResourceLink>
              <button class="button danger" type="button" :disabled="pendingRun === run.id" @click="openRunActionConfirm(run, 'cancel')">{{ t("cancel") }}</button>
              <button class="button" type="button" :disabled="pendingRun === run.id" @click="openRunActionConfirm(run, 'retry')">{{ t("retry") }}</button>
              <button class="button" type="button" :disabled="pendingRun === run.id" @click="openRunActionConfirm(run, 'replay')">{{ t("replay") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <DangerConfirmDialog
      :open="Boolean(runActionTarget)"
      :title="t('confirmRunAction')"
      :message="t('confirmRunActionCopy')"
      :items="runActionConfirmItems"
      :confirm-label="runAction ? runActionLabel(runAction) : t('confirm')"
      :cancel-label="t('back')"
      :busy-label="t('saving')"
      :busy="Boolean(runActionTarget && pendingRun === runActionTarget.id)"
      :error="runActionError"
      @cancel="closeRunActionConfirm"
      @confirm="runConfirmedRunAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const runActionError = ref<ConsoleApiError | null>(null);
const runs = ref<Run[]>([]);
const query = ref("");
const status = ref("");
const runActionTarget = ref<Run | null>(null);
const runAction = ref<string | null>(null);
const pendingRun = ref<number | null>(null);

const filteredRuns = computed(() =>
  runs.value.filter((run) => {
    const matchesQuery = `${run.id} ${run.agent}`.toLowerCase().includes(query.value.toLowerCase());
    const matchesStatus = status.value ? run.status === status.value : true;
    return matchesQuery && matchesStatus;
  }),
);
const runActionConfirmItems = computed(() => runActionTarget.value && runAction.value ? [
  { label: t("run"), value: String(runActionTarget.value.id) },
  { label: t("status"), value: runActionTarget.value.status },
  { label: t("operations"), value: runActionLabel(runAction.value) },
] : []);

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

function formatLatency(value: number | null): string {
  return typeof value === "number" ? `${value} ms` : "-";
}

function formatCost(value: number | undefined): string {
  return typeof value === "number" ? `$${value.toFixed(3)}` : "-";
}

function openRunActionConfirm(run: Run, operation: string) {
  runActionTarget.value = run;
  runAction.value = operation;
  runActionError.value = null;
}

function closeRunActionConfirm() {
  if (runActionTarget.value && pendingRun.value === runActionTarget.value.id) return;
  runActionTarget.value = null;
  runAction.value = null;
  runActionError.value = null;
}

function runActionLabel(operation: string): string {
  if (operation === "cancel") return t("cancel");
  if (operation === "retry") return t("retry");
  if (operation === "replay") return t("replay");
  return operation;
}

async function runConfirmedRunAction() {
  if (!runActionTarget.value || !runAction.value) return;
  pendingRun.value = runActionTarget.value.id;
  error.value = null;
  runActionError.value = null;
  try {
    const updated = await consoleClient.controlRun(runActionTarget.value.id, runAction.value);
    if (runAction.value === "replay") {
      runs.value = [updated, ...runs.value.filter((run) => run.id !== updated.id)];
    } else {
      runs.value = runs.value.map((run) => (run.id === updated.id ? updated : run));
    }
    runActionTarget.value = null;
    runAction.value = null;
  } catch (caught) {
    runActionError.value = toConsoleApiError(caught);
  } finally {
    pendingRun.value = null;
  }
}
</script>

<style scoped>
.actions-cell {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
