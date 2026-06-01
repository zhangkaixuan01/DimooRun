<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("leaseRetryDeadLetter") }}</p>
        <h1 class="page-title">{{ t("tasks") }}</h1>
      </div>
      <div class="toolbar">
        <select class="select"><option>{{ t("allQueues") }}</option><option>runtime.prod</option></select>
        <select class="select"><option>{{ t("allStatus") }}</option><option>leased</option><option>dead_letter</option></select>
      </div>
    </header>
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && tasks.length === 0" />
    <div v-if="mode !== 'offline' && !loading && !error && tasks.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("tasks") }}</th><th>{{ t("run") }}</th><th>{{ t("status") }}</th><th>{{ t("attempt") }}</th><th>{{ t("queue") }}</th><th>{{ t("worker") }}</th><th>{{ t("heartbeat") }}</th><th>{{ t("leaseUntil") }}</th><th>{{ t("fencing") }}</th><th>{{ t("retry") }}</th><th>{{ t("deadLetter") }}</th><th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td class="mono">{{ task.id }}</td>
            <td><ResourceLink :to="`/runs/${task.runId}`">{{ task.runId }}</ResourceLink></td>
            <td><StatusBadge :status="task.status" :label="task.status" /></td>
            <td>{{ task.attempt }}</td>
            <td>{{ task.queue }}</td>
            <td>{{ task.workerId }}</td>
            <td>{{ task.heartbeatAt }}</td>
            <td>{{ task.leaseUntil }}</td>
            <td>{{ task.fencingToken }}</td>
            <td>{{ task.retryCount }}</td>
            <td>{{ task.deadLetterReason ?? "-" }}</td>
            <td><button class="button danger" type="button" :disabled="pendingTask === task.id" @click="cancelTask(task.id)">{{ t("cancel") }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Task } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const tasks = ref<Task[]>([]);
const pendingTask = ref<number | null>(null);

async function loadTasks() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    tasks.value = (await consoleClient.listTasks()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function cancelTask(taskId: number) {
  pendingTask.value = taskId;
  error.value = null;
  try {
    const updated = await consoleClient.cancelTask(taskId);
    tasks.value = tasks.value.map((task) => (task.id === taskId ? updated : task));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingTask.value = null;
  }
}

onMounted(loadTasks);
</script>
