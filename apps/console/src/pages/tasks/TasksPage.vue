<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("leaseRetryDeadLetter") }}</p>
        <h1 class="page-title">{{ t("tasks") }}</h1>
      </div>
      <div class="toolbar">
        <select v-model="queueFilter" class="select">
          <option value="">{{ t("allQueues") }}</option>
          <option v-for="queue in queueOptions" :key="queue" :value="queue">{{ queue }}</option>
        </select>
        <select v-model="statusFilter" class="select">
          <option value="">{{ t("allStatus") }}</option>
          <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
        </select>
      </div>
    </header>
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && tasks.length === 0" />
    <div v-if="mode !== 'offline' && !loading && !error && filteredTasks.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("tasks") }}</th><th>{{ t("run") }}</th><th>{{ t("status") }}</th><th>{{ t("attempt") }}</th><th>{{ t("queue") }}</th><th>{{ t("worker") }}</th><th>{{ t("heartbeat") }}</th><th>{{ t("leaseUntil") }}</th><th>{{ t("fencing") }}</th><th>{{ t("retry") }}</th><th>{{ t("deadLetter") }}</th><th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in filteredTasks" :key="task.id">
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
            <td class="actions-cell">
              <button class="button" type="button" @click="openTaskDetail(task)">{{ t("view") }}</button>
              <button class="button danger" type="button" :disabled="pendingTask === task.id" @click="openCancelTaskConfirm(task)">{{ t("cancel") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="detailTask" class="drawer-layer" @click.self="closeTaskDetail">
        <aside class="drawer wide-drawer" :aria-label="t('details')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("tasks") }}</p>
              <h2>Task #{{ detailTask.id }}</h2>
            </div>
          </header>
          <div class="drawer-form">
            <dl class="detail-list">
              <div>
                <dt>{{ t("run") }}</dt>
                <dd><ResourceLink :to="`/runs/${detailTask.runId}`">{{ detailTask.runId }}</ResourceLink></dd>
              </div>
              <div>
                <dt>{{ t("status") }}</dt>
                <dd><StatusBadge :status="detailTask.status" :label="detailTask.status" /></dd>
              </div>
              <div>
                <dt>{{ t("queue") }}</dt>
                <dd>{{ detailTask.queue }}</dd>
              </div>
              <div>
                <dt>{{ t("attempt") }}</dt>
                <dd>{{ detailTask.attempt }}</dd>
              </div>
              <div>
                <dt>{{ t("worker") }}</dt>
                <dd class="mono">{{ detailTask.workerId }}</dd>
              </div>
              <div>
                <dt>{{ t("heartbeat") }}</dt>
                <dd class="mono">{{ detailTask.heartbeatAt || "-" }}</dd>
              </div>
              <div>
                <dt>{{ t("leaseUntil") }}</dt>
                <dd class="mono">{{ detailTask.leaseUntil || "-" }}</dd>
              </div>
              <div>
                <dt>{{ t("fencing") }}</dt>
                <dd>{{ detailTask.fencingToken }}</dd>
              </div>
              <div>
                <dt>{{ t("deadLetter") }}</dt>
                <dd>{{ detailTask.deadLetterReason ?? "-" }}</dd>
              </div>
            </dl>
            <label>
              <span>{{ t("metadata") }}</span>
              <pre>{{ formatJson(taskMetadata(detailTask)) }}</pre>
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeTaskDetail">{{ t("cancel") }}</button>
              <button class="button danger" type="button" :disabled="pendingTask === detailTask.id" @click="openCancelTaskConfirm(detailTask)">
                {{ t("cancel") }}
              </button>
            </div>
          </div>
        </aside>
      </div>
    </Teleport>

    <DangerConfirmDialog
      :open="Boolean(cancelTaskTarget)"
      :title="t('confirmTaskCancel')"
      :message="t('confirmTaskCancelCopy')"
      :items="cancelTaskConfirmItems"
      :confirm-label="t('cancel')"
      :cancel-label="t('back')"
      :busy-label="t('saving')"
      :busy="Boolean(cancelTaskTarget && pendingTask === cancelTaskTarget.id)"
      :error="cancelTaskError"
      @cancel="closeCancelTaskConfirm"
      @confirm="runConfirmedCancelTask"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Task } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const cancelTaskError = ref<ConsoleApiError | null>(null);
const tasks = ref<Task[]>([]);
const cancelTaskTarget = ref<Task | null>(null);
const detailTask = ref<Task | null>(null);
const pendingTask = ref<number | null>(null);
const queueFilter = ref("");
const statusFilter = ref("");
const queueOptions = computed(() => [...new Set(tasks.value.map((task) => task.queue))].sort());
const statusOptions = computed(() => [...new Set(tasks.value.map((task) => task.status))].sort());
const cancelTaskConfirmItems = computed(() => cancelTaskTarget.value ? [
  { label: t("tasks"), value: String(cancelTaskTarget.value.id) },
  { label: t("run"), value: String(cancelTaskTarget.value.runId) },
  { label: t("status"), value: cancelTaskTarget.value.status },
] : []);
const filteredTasks = computed(() =>
  tasks.value.filter((task) => {
    const matchesQueue = queueFilter.value ? task.queue === queueFilter.value : true;
    const matchesStatus = statusFilter.value ? task.status === statusFilter.value : true;
    return matchesQueue && matchesStatus;
  }),
);

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

function openCancelTaskConfirm(task: Task) {
  cancelTaskTarget.value = task;
  cancelTaskError.value = null;
}

function openTaskDetail(task: Task) {
  detailTask.value = task;
}

function closeTaskDetail() {
  detailTask.value = null;
}

function closeCancelTaskConfirm() {
  if (cancelTaskTarget.value && pendingTask.value === cancelTaskTarget.value.id) return;
  cancelTaskTarget.value = null;
  cancelTaskError.value = null;
}

async function runConfirmedCancelTask() {
  if (!cancelTaskTarget.value) return;
  pendingTask.value = cancelTaskTarget.value.id;
  error.value = null;
  cancelTaskError.value = null;
  try {
    const updated = await consoleClient.cancelTask(cancelTaskTarget.value.id);
    tasks.value = tasks.value.map((task) => (task.id === updated.id ? updated : task));
    if (detailTask.value?.id === updated.id) {
      detailTask.value = updated;
    }
    cancelTaskTarget.value = null;
  } catch (caught) {
    cancelTaskError.value = toConsoleApiError(caught);
  } finally {
    pendingTask.value = null;
  }
}

onMounted(loadTasks);

function taskMetadata(task: Task): Record<string, unknown> {
  return {
    partitionKey: task.partitionKey ?? null,
    resourceClass: task.resourceClass ?? null,
    quotaBlockingReason: task.quotaBlockingReason ?? null,
    retryCount: task.retryCount,
  };
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
</script>

<style scoped>
.actions-cell {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.drawer-layer {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  justify-content: flex-end;
  background: oklch(18% 0.017 248 / 36%);
}

.drawer {
  display: grid;
  width: min(480px, 100%);
  grid-template-rows: auto 1fr;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.wide-drawer {
  width: min(620px, 100%);
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 18px;
}

.drawer-header h2 {
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
}

.drawer-form {
  display: grid;
  align-content: start;
  gap: 14px;
  overflow: auto;
  padding: 18px;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  margin: 8px -18px -18px;
  padding: 14px 18px;
}

.detail-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.detail-list dt,
label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.detail-list dd {
  margin: 4px 0 0;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

pre {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

@media (max-width: 760px) {
  .detail-list {
    grid-template-columns: 1fr;
  }

  .drawer {
    width: 100%;
  }
}
</style>
