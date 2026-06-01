<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("approvalResume") }}</p>
        <h1 class="page-title">{{ t("humanTasks") }}</h1>
      </div>
    </header>
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && humanTasks.length === 0" />
    <div v-if="mode !== 'offline' && !loading && !error && humanTasks.length > 0" class="table-wrap">
      <table>
        <thead><tr><th>{{ t("tasks") }}</th><th>{{ t("source") }}</th><th>{{ t("risk") }}</th><th>{{ t("status") }}</th><th>{{ t("assignee") }}</th><th>{{ t("expires") }}</th><th>{{ t("actions") }}</th></tr></thead>
        <tbody>
          <tr v-for="task in humanTasks" :key="task.id">
            <td class="mono">{{ task.id }}</td>
            <td>{{ task.source }}</td>
            <td><StatusBadge :status="task.risk === 'critical' ? 'failed' : 'pending'" :label="task.risk" /></td>
            <td><StatusBadge :status="task.status" :label="task.status" /></td>
            <td>{{ task.assignee }}</td>
            <td>{{ formatDateTime(task.expiresAt) }}</td>
            <td class="ops">
              <button class="button" type="button" :disabled="pendingTask === task.id" @click="decide(task.id, 'approve')">{{ t("approve") }}</button>
              <button class="button danger" type="button" :disabled="pendingTask === task.id" @click="decide(task.id, 'reject')">{{ t("reject") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { HumanTask } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const pendingTask = ref<number | null>(null);
const humanTasks = ref<HumanTask[]>([]);

async function loadHumanTasks() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    humanTasks.value = (await consoleClient.listHumanTasks()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function decide(taskId: number, decision: "approve" | "reject") {
  pendingTask.value = taskId;
  error.value = null;
  try {
    const updated = await consoleClient.decideHumanTask(taskId, decision);
    humanTasks.value = humanTasks.value.map((task) => (task.id === taskId ? updated : task));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingTask.value = null;
  }
}

onMounted(loadHumanTasks);
</script>

<style scoped>
.ops {
  display: flex;
  gap: 8px;
}
</style>
