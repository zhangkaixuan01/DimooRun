<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Observability</p>
        <h1 class="page-title">{{ config.title }}</h1>
        <p class="page-subtitle">{{ config.subtitle }}</p>
      </div>
      <button class="button" type="button" :disabled="loading" @click="load">
        {{ loading ? "Loading" : "Refresh" }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !error && rows.length === 0" />

    <section v-if="mode !== 'offline'" class="panel filters-panel">
      <form class="filters-grid" @submit.prevent="load">
        <label v-if="config.filter === 'actor'">
          <span>Actor</span>
          <input v-model="filters.actor" class="input" placeholder="operator" />
        </label>
        <label v-if="config.filter === 'sentiment'">
          <span>Sentiment</span>
          <select v-model="filters.sentiment" class="input">
            <option value="">Any</option>
            <option value="positive">positive</option>
            <option value="negative">negative</option>
            <option value="neutral">neutral</option>
          </select>
        </label>
        <label v-if="config.filter === 'status'">
          <span>Status</span>
          <select v-model="filters.status" class="input">
            <option value="">Any</option>
            <option value="succeeded">succeeded</option>
            <option value="failed">failed</option>
            <option value="pending">pending</option>
            <option value="retrying">retrying</option>
          </select>
        </label>
        <label>
          <span>Run</span>
          <input v-model="filters.run_id" class="input" inputmode="numeric" placeholder="1001" />
        </label>
        <label>
          <span>Deployment</span>
          <input v-model="filters.deployment_id" class="input" inputmode="numeric" placeholder="10" />
        </label>
        <button class="button primary" type="submit" :disabled="loading">Apply filters</button>
      </form>
    </section>

    <InlineApiError :error="error" />

    <section v-if="mode !== 'offline' && !loading && !error && rows.length > 0" class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ config.tableTitle }}</h2>
          <p class="panel-copy">{{ rows.length }} item(s)</p>
        </div>
      </div>
      <div class="panel-body">
        <DataTable :columns="columns" :rows="rows" row-key="id" :label="config.tableTitle">
          <template #cell-id="{ row }">
            <span class="mono">#{{ row.id }}</span>
          </template>
          <template #cell-primary="{ row }">
            <strong>{{ primaryValue(row) }}</strong>
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :status="String(row.status || row.result || 'active')" :label="String(row.status || row.result || 'active')" />
          </template>
          <template #cell-run="{ row }">
            <span v-if="row.run_id" class="mono">Run #{{ row.run_id }}</span>
            <span v-else class="muted">-</span>
          </template>
          <template #cell-secondary="{ row }">
            <span class="muted">{{ secondaryValue(row) }}</span>
          </template>
          <template #cell-created="{ row }">
            {{ formatDateTime(String(row.created_at || row.updated_at || "")) }}
          </template>
          <template #cell-actions="{ row }">
            <button class="button" type="button" @click="selected = row">{{ config.actionLabel }}</button>
          </template>
        </DataTable>
      </div>
    </section>

    <AppDrawer
      :open="Boolean(selected)"
      :label="config.drawerTitle"
      :title="config.drawerTitle"
      kicker="Observability"
      width="wide"
      @close="selected = null"
    >
      <div v-if="selected" class="drawer-content">
        <dl class="detail-grid">
          <div>
            <dt>ID</dt>
            <dd class="mono">#{{ selected.id }}</dd>
          </div>
          <div v-if="selected.run_id">
            <dt>{{ config.kind === "replay-jobs" ? "Source run" : "Run" }}</dt>
            <dd>
              <RouterLink :to="`/runs/${selected.run_id}`">Run #{{ selected.run_id }}</RouterLink>
            </dd>
          </div>
          <div v-if="selected.deployment_id">
            <dt>Deployment</dt>
            <dd>
              <RouterLink :to="`/deployments/${selected.deployment_id}`">Deployment #{{ selected.deployment_id }}</RouterLink>
            </dd>
          </div>
          <div v-if="selected.policy_id">
            <dt>Policy</dt>
            <dd class="mono">#{{ selected.policy_id }}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd><StatusBadge :status="String(selected.status || selected.result || 'active')" :label="String(selected.status || selected.result || 'active')" /></dd>
          </div>
        </dl>
        <pre class="json-preview">{{ formatJson(selected) }}</pre>
        <div v-if="config.kind === 'replay-jobs'" class="drawer-actions">
          <button class="button primary" type="button">Retry replay</button>
        </div>
      </div>
    </AppDrawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import DataTable from "../../components/DataTable.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { formatDateTime } from "../../utils/dateTime";

type WorkbenchKind = "audit-logs" | "artifacts" | "evaluations" | "feedback" | "replay-jobs";

const props = defineProps<{
  kind: WorkbenchKind;
}>();

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const rows = ref<AdminResource[]>([]);
const selected = ref<AdminResource | null>(null);
const filters = reactive<Record<string, string>>({
  actor: "",
  sentiment: "",
  status: "",
  run_id: "",
  deployment_id: "",
});

const columns = [
  { key: "id", label: "ID" },
  { key: "primary", label: "Name" },
  { key: "status", label: "Status" },
  { key: "run", label: "Run" },
  { key: "secondary", label: "Evidence" },
  { key: "created", label: "Created" },
  { key: "actions", label: "Actions" },
];

const config = computed(() => {
  switch (props.kind) {
    case "audit-logs":
      return {
        kind: props.kind,
        title: "Audit Log Workbench",
        subtitle: "Filter governance and security decisions, then inspect linked runtime evidence.",
        tableTitle: "Audit events",
        drawerTitle: "Audit evidence",
        actionLabel: "Open evidence",
        filter: "actor",
      };
    case "artifacts":
      return {
        kind: props.kind,
        title: "Artifact Workbench",
        subtitle: "Inspect artifact metadata and trace each file back to the run that produced it.",
        tableTitle: "Artifacts",
        drawerTitle: "Artifact detail",
        actionLabel: "Inspect artifact",
        filter: "status",
      };
    case "evaluations":
      return {
        kind: props.kind,
        title: "Evaluation Workbench",
        subtitle: "Compare passed and failed evaluation results across datasets and experiments.",
        tableTitle: "Evaluation results",
        drawerTitle: "Evaluation result",
        actionLabel: "Open result",
        filter: "status",
      };
    case "feedback":
      return {
        kind: props.kind,
        title: "Feedback Workbench",
        subtitle: "Triage user feedback with the run evidence needed to reproduce or replay issues.",
        tableTitle: "Feedback",
        drawerTitle: "Feedback detail",
        actionLabel: "Open feedback",
        filter: "sentiment",
      };
    case "replay-jobs":
      return {
        kind: props.kind,
        title: "Replay Jobs Workbench",
        subtitle: "Track replay status, origin IDs, and retry evidence from one operator surface.",
        tableTitle: "Replay jobs",
        drawerTitle: "Replay job detail",
        actionLabel: "Inspect replay job",
        filter: "status",
      };
  }
});

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const activeFilters = {
      actor: filters.actor,
      sentiment: filters.sentiment,
      status: filters.status,
      run_id: filters.run_id,
      deployment_id: filters.deployment_id,
    };
    const response = await listForKind(activeFilters);
    rows.value = response.items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function listForKind(activeFilters: Record<string, string>) {
  switch (props.kind) {
    case "audit-logs":
      return consoleClient.listAuditLogs(activeFilters);
    case "artifacts":
      return consoleClient.listArtifacts(activeFilters);
    case "evaluations":
      return consoleClient.listEvaluationResults(activeFilters);
    case "feedback":
      return consoleClient.listFeedback(activeFilters);
    case "replay-jobs":
      return consoleClient.listReplayJobs(activeFilters);
  }
}

function primaryValue(row: AdminResource): string {
  return String(row.action || row.name || row.label || row.artifact_type || row.metric || row.source || `item-${row.id}`);
}

function secondaryValue(row: AdminResource): string {
  if (props.kind === "replay-jobs" && row.run_id) return `Source run #${row.run_id}`;
  if (props.kind === "evaluations" && row.metric) return String(row.metric);
  return String(row.actor || row.storage_ref || row.dataset_name || row.sentiment || row.request_id || "-");
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

onMounted(load);
</script>

<style scoped>
.filters-panel {
  padding: 14px 16px;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr)) auto;
  gap: 12px;
  align-items: end;
}

.filters-grid label {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.drawer-content {
  display: grid;
  gap: 16px;
  padding: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.detail-grid div {
  display: grid;
  gap: 4px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

.detail-grid dt {
  color: var(--color-text-muted);
  font-size: 12px;
}

.detail-grid dd {
  margin: 0;
}

.json-preview {
  max-height: 360px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
  font-size: 12px;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1100px) {
  .filters-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .filters-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
