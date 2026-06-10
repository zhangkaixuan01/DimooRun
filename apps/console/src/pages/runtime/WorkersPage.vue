<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime Operations</p>
        <h1 class="page-title">Workers</h1>
        <p class="page-subtitle">
          Heartbeat, queue ownership, safe drain controls, and restart decisions.
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && workers.length === 0" />

    <div v-if="mode !== 'offline' && !loading && workers.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Worker</th>
            <th>Status</th>
            <th>Drain</th>
            <th>Queues</th>
            <th>Capacity</th>
            <th>Active</th>
            <th>Heartbeat</th>
            <th>Version</th>
            <th>Last error</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="worker in workers"
            :key="worker.workerId"
            class="selectable-row"
            :data-selected="selectedWorker?.workerId === worker.workerId ? 'true' : 'false'"
            tabindex="0"
            @click="selectWorker(worker.workerId)"
            @keydown.enter="selectWorker(worker.workerId)"
            @keydown.space.prevent="selectWorker(worker.workerId)"
          >
            <td class="mono">{{ worker.workerId }}</td>
            <td>
              <StatusBadge :status="worker.readiness === 'ready' ? 'ready' : 'degraded'" :label="worker.readiness" />
            </td>
            <td>{{ worker.drainStatus }}</td>
            <td>{{ worker.queues.join(", ") }}</td>
            <td>{{ worker.activeAttempts }} / {{ worker.capacity }}</td>
            <td>{{ worker.activeRuns }}</td>
            <td>{{ formatSeconds(worker.heartbeatAgeSeconds) }}</td>
            <td>{{ worker.version }}</td>
            <td>{{ worker.lastError || "none" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="selectedWorker" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">Worker detail</p>
          <h2 class="panel-title">{{ selectedWorker.workerId }}</h2>
          <p class="muted">{{ selectedWorker.environment }} / {{ selectedWorker.version }}</p>
        </div>
      </div>
      <div class="panel-body detail-grid">
        <aside class="summary">
          <dl>
            <div>
              <dt>Liveness</dt>
              <dd>{{ selectedWorker.liveness }}</dd>
            </div>
            <div>
              <dt>Readiness</dt>
              <dd>{{ selectedWorker.readiness }}</dd>
            </div>
            <div>
              <dt>Drain status</dt>
              <dd>{{ selectedWorker.drainStatus }}</dd>
            </div>
            <div>
              <dt>Active runs</dt>
              <dd>{{ selectedWorker.activeRuns }}</dd>
            </div>
            <div>
              <dt>Retrying tasks</dt>
              <dd>{{ selectedWorker.retryingTasks }}</dd>
            </div>
            <div>
              <dt>Dead letters</dt>
              <dd>{{ selectedWorker.deadLetterTasks }}</dd>
            </div>
          </dl>
        </aside>

        <div class="workspace">
          <section class="child-panel">
            <div class="actions-grid">
              <button
                v-for="action in selectedWorker.actions"
                :key="action.action"
                class="button"
                :class="{ danger: action.action === 'quarantine' }"
                type="button"
                :disabled="action.available === false || pendingAction === action.action"
                @click="openConfirm(action.action)"
              >
                {{ action.label }}
              </button>
            </div>
            <div class="reasons">
              <p
                v-for="action in selectedWorker.actions.filter((item) => item.disabledReasons.length > 0)"
                :key="`${action.action}-reason`"
                class="form-error"
              >
                {{ action.label }}: {{ action.disabledReasons[0] }}
              </p>
            </div>
          </section>

          <section class="child-panel">
            <h3>Assignments</h3>
            <div class="link-grid">
              <p v-for="runId in selectedWorker.activeRunIds" :key="`run-${runId}`">
                <ResourceLink :to="`/runs/${runId}`">Run #{{ runId }}</ResourceLink>
              </p>
              <p v-if="selectedWorker.activeRunIds.length === 0" class="muted">No active runs.</p>
            </div>
            <div class="link-grid">
              <p v-for="deploymentId in selectedWorker.deploymentIds" :key="`dep-${deploymentId}`">
                <ResourceLink :to="`/deployments/${deploymentId}`">Deployment #{{ deploymentId }}</ResourceLink>
              </p>
            </div>
          </section>
        </div>
      </div>
    </section>

    <ConfirmImpactDialog
      v-if="selectedWorker"
      :open="dialogOpen"
      :title="confirmActionLabel"
      :impact-target="selectedWorker.workerId"
      :environment="selectedWorker.environment"
      :affects-new-runs="true"
      :affects-existing-runs="confirmActionName !== 'restart-request'"
      :writes-audit-log="true"
      :rollbackable="confirmActionName === 'drain'"
      @cancel="dialogOpen = false"
      @confirm="confirmAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
} from "../../api/client";
import { createMutationAction } from "../../api/mutations";
import type { RuntimeControlAction, RuntimeWorker, RuntimeWorkerDetail } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ConfirmImpactDialog from "../../components/ConfirmImpactDialog.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const route = useRoute();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const workers = ref<RuntimeWorker[]>([]);
const selectedWorker = ref<RuntimeWorkerDetail | null>(null);
const dialogOpen = ref(false);
const confirmActionName = ref("");
const pendingAction = ref<string | null>(null);

const confirmActionLabel = computed(() => {
  const action = selectedWorker.value?.actions.find((item) => item.action === confirmActionName.value);
  return action?.label || confirmActionName.value;
});

const controlWorkerMutation = createMutationAction(
  async (payload: { workerId: string; action: string }, context) =>
    consoleClient.controlRuntimeWorker(payload.workerId, payload.action, context),
);

async function loadWorkers(selectedId?: string) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    workers.value = (await consoleClient.listRuntimeWorkers()).items;
    const nextId = selectedId || String(route.query.worker || "") || workers.value[0]?.workerId;
    if (nextId) {
      await selectWorker(nextId);
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function selectWorker(workerId: string) {
  try {
    selectedWorker.value = await consoleClient.getRuntimeWorker(workerId);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
}

function openConfirm(action: string) {
  confirmActionName.value = action;
  dialogOpen.value = true;
}

async function confirmAction() {
  if (!selectedWorker.value || !confirmActionName.value) return;
  pendingAction.value = confirmActionName.value;
  error.value = null;
  try {
    selectedWorker.value = await controlWorkerMutation.run(
      {
        workerId: selectedWorker.value.workerId,
        action: confirmActionName.value,
      },
      { auditReason: `${confirmActionName.value} worker from console` },
    );
    await loadWorkers(selectedWorker.value.workerId);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingAction.value = null;
    dialogOpen.value = false;
  }
}

function formatSeconds(value: number | null): string {
  if (value === null) return "n/a";
  return `${Math.round(value)}s`;
}

onMounted(async () => {
  await loadWorkers();
});
</script>

<style scoped>
.selectable-row {
  cursor: pointer;
}

.selectable-row[data-selected="true"] {
  background: var(--color-accent-soft);
}

.detail-panel {
  margin-top: 16px;
}

.section-kicker {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  text-transform: uppercase;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 16px;
}

.summary {
  border-right: 1px solid var(--color-border);
  padding-right: 16px;
}

.summary dl,
.workspace,
.child-panel,
.link-grid,
.reasons {
  display: grid;
  gap: 12px;
}

.summary dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
}

.summary dd {
  margin: 4px 0 0;
}

.actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 16px;
  }
}
</style>
