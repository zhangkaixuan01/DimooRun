<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("approvalResume") }}</p>
        <h1 class="page-title">{{ t("humanTasks") }}</h1>
      </div>
    </header>
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && humanTasks.length === 0" />
    <div v-if="mode !== 'offline' && !loading && !error && humanTasks.length > 0" class="task-list">
      <table>
        <thead><tr><th>{{ t("tasks") }}</th><th>{{ t("source") }}</th><th>{{ t("risk") }}</th><th>{{ t("requester") }}</th><th>{{ t("status") }}</th><th>{{ t("assignee") }}</th><th>{{ t("resumeOutcome") }}</th><th>{{ t("actions") }}</th></tr></thead>
        <tbody>
          <tr v-for="task in humanTasks" :key="task.id">
            <td class="mono">{{ task.id }}</td>
            <td>
              <strong>{{ task.source }}</strong>
              <span class="muted line">{{ task.riskReason }}</span>
              <span class="muted line">{{ formatDiff(task.diff) }}</span>
            </td>
            <td><StatusBadge :status="task.risk === 'critical' ? 'failed' : 'pending'" :label="task.risk" /></td>
            <td>{{ task.requester }}</td>
            <td><StatusBadge :status="task.status" :label="task.status" /></td>
            <td>{{ task.assignee }}</td>
            <td>{{ formatResume(task) }}</td>
            <td class="ops">
              <label class="comment-label">
                <span>{{ t("decisionComment") }}</span>
                <input
                  v-model="comments[task.id]"
                  class="input"
                  :aria-label="`${t('decisionComment')} for task ${task.id}`"
                />
              </label>
              <button class="button" type="button" :disabled="pendingTask === task.id" @click="decide(task.id, 'approve')">{{ t("approveTask") }} {{ task.id }}</button>
              <button class="button danger" type="button" :disabled="pendingTask === task.id" @click="decide(task.id, 'reject')">{{ t("rejectTask") }} {{ task.id }}</button>
              <span v-if="task.decision.comment" class="muted decision-note">{{ task.decision.comment }}</span>
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

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const pendingTask = ref<number | null>(null);
const humanTasks = ref<HumanTask[]>([]);
const comments = ref<Record<number, string>>({});

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
    const updated = await consoleClient.decideHumanTask(taskId, decision, comments.value[taskId] || "");
    humanTasks.value = humanTasks.value.map((task) => (task.id === taskId ? updated : task));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingTask.value = null;
  }
}

function formatDiff(diff: Record<string, unknown>): string {
  const desiredStatus = diff.desired_status;
  if (desiredStatus && typeof desiredStatus === "object" && !Array.isArray(desiredStatus)) {
    const values = desiredStatus as { from?: unknown; to?: unknown };
    return `desired_status: ${String(values.from)} -> ${String(values.to)}`;
  }
  const entries = Object.entries(diff);
  if (entries.length === 0) return "";
  return entries.map(([key, value]) => `${key}: ${JSON.stringify(value)}`).join(", ");
}

function formatResume(task: HumanTask): string {
  return `Resume: ${task.resumeOutcome.status}`;
}

onMounted(loadHumanTasks);
</script>

<style scoped>
.task-list {
  overflow: auto;
}

.line,
.decision-note {
  display: block;
  margin-top: 4px;
}

.ops {
  display: grid;
  gap: 8px;
  min-width: 260px;
}

.comment-label {
  display: grid;
  gap: 4px;
}

.comment-label span {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 700;
}
</style>
