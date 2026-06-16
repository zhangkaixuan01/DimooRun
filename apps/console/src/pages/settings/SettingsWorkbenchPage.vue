<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Settings</p>
        <h1 class="page-title">{{ config.title }}</h1>
        <p class="page-subtitle">{{ config.subtitle }}</p>
      </div>
      <button class="button" type="button" :disabled="loading" @click="load">
        {{ loading ? "Loading" : "Refresh" }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !error && rows.length === 0" />
    <InlineApiError :error="error" />

    <section v-if="!loading && !error && rows.length > 0" class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ config.tableTitle }}</h2>
          <p class="panel-copy">{{ rows.length }} item(s)</p>
        </div>
      </div>
      <div class="panel-body">
        <DataTable :columns="columns" :rows="rows" row-key="id" :label="config.tableTitle">
          <template #cell-name="{ row }">
            <strong>{{ primaryValue(row) }}</strong>
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :status="String(row.status || 'active')" :label="String(row.status || 'active')" />
          </template>
          <template #cell-detail="{ row }">
            <span class="muted">{{ secondaryValue(row) }}</span>
          </template>
          <template #cell-updated="{ row }">
            {{ formatDateTime(String(row.updated_at || row.created_at || "")) }}
          </template>
          <template #cell-actions="{ row }">
            <button class="button primary" type="button" @click="runAction(row)">
              {{ config.actionLabel }}
            </button>
          </template>
        </DataTable>
      </div>
    </section>

    <AppDrawer
      :open="Boolean(selected && actionResult)"
      :label="config.drawerTitle"
      :title="config.drawerTitle"
      kicker="Settings"
      width="wide"
      @close="closeDrawer"
    >
      <div v-if="selected && actionResult" class="drawer-content">
        <dl class="detail-grid">
          <div>
            <dt>name</dt>
            <dd>{{ primaryValue(selected) }}</dd>
          </div>
          <div>
            <dt>status</dt>
            <dd>
              <StatusBadge :status="String(selected.status || 'active')" :label="String(selected.status || 'active')" />
            </dd>
          </div>
          <template v-if="props.kind === 'observability-exporters'">
            <div>
              <dt>validation status</dt>
              <dd>{{ actionResult.validation_status }}</dd>
            </div>
            <div>
              <dt>last proof</dt>
              <dd>{{ actionResult.last_proof_at || "n/a" }}</dd>
            </div>
            <div>
              <dt>target ref</dt>
              <dd class="mono">{{ actionResult.target_ref_redacted }}</dd>
            </div>
            <div>
              <dt>blocked reason</dt>
              <dd>{{ actionResult.blocked_reason || "none" }}</dd>
            </div>
          </template>
          <template v-else-if="props.kind === 'semantic-store'">
            <div>
              <dt>provider status</dt>
              <dd>{{ actionResult.provider_status }}</dd>
            </div>
            <div>
              <dt>index coverage</dt>
              <dd>{{ summarizeIndexCoverage(actionResult.index_coverage) }}</dd>
            </div>
            <div>
              <dt>embedding model</dt>
              <dd>{{ actionResult.embedding_model }}</dd>
            </div>
            <div>
              <dt>last proof</dt>
              <dd>{{ actionResult.last_validation_proof || "n/a" }}</dd>
            </div>
          </template>
          <template v-else-if="props.kind === 'sandbox-policies'">
            <div>
              <dt>blocked capabilities</dt>
              <dd>{{ summarizeList(actionResult.blocked_capabilities) }}</dd>
            </div>
            <div>
              <dt>audit reason required</dt>
              <dd>{{ actionResult.audit_required ? "true" : "false" }}</dd>
            </div>
            <div class="detail-span">
              <dt>affected runtime surfaces</dt>
              <dd>{{ summarizeList(actionResult.affected_runtime_surfaces) }}</dd>
            </div>
          </template>
          <template v-else>
            <div>
              <dt>warm capacity</dt>
              <dd>{{ actionResult.warm_capacity }}</dd>
            </div>
            <div>
              <dt>scale limit</dt>
              <dd>{{ actionResult.scale_limit }}</dd>
            </div>
            <div>
              <dt>estimated saturation</dt>
              <dd>{{ formatRatio(actionResult.estimated_saturation) }}</dd>
            </div>
            <div class="detail-span">
              <dt>affected worker pools</dt>
              <dd>{{ summarizeList(actionResult.affected_worker_pools) }}</dd>
            </div>
          </template>
        </dl>

        <section class="evidence-panel">
          <h2 class="panel-title">{{ config.evidenceTitle }}</h2>
          <pre class="json-preview">{{ formatJson(actionResult) }}</pre>
        </section>
      </div>
    </AppDrawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import DataTable from "../../components/DataTable.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { formatDateTime } from "../../utils/dateTime";

type SettingsWorkbenchKind =
  | "observability-exporters"
  | "semantic-store"
  | "sandbox-policies"
  | "container-pool-policies";

const props = defineProps<{
  kind: SettingsWorkbenchKind;
}>();

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const rows = ref<AdminResource[]>([]);
const selected = ref<AdminResource | null>(null);
const actionResult = ref<Record<string, any> | null>(null);

const columns = [
  { key: "name", label: "Name" },
  { key: "status", label: "Status" },
  { key: "detail", label: "Configuration" },
  { key: "updated", label: "Updated" },
  { key: "actions", label: "Actions" },
];

const config = computed(() => {
  switch (props.kind) {
    case "observability-exporters":
      return {
        title: "Observability Exporters",
        subtitle: "Validate OTLP endpoints, proof timestamps, and redacted delivery targets from one operator surface.",
        tableTitle: "Exporters",
        actionLabel: "Validate exporter",
        drawerTitle: "Exporter validation",
        evidenceTitle: "configuration summary",
      };
    case "semantic-store":
      return {
        title: "Semantic Store Providers",
        subtitle: "Review embedding providers, index coverage, and local readiness before changing runtime defaults.",
        tableTitle: "Providers",
        actionLabel: "Validate provider",
        drawerTitle: "Provider validation",
        evidenceTitle: "provider evidence",
      };
    case "sandbox-policies":
      return {
        title: "Sandbox Policies",
        subtitle: "Preview enforcement outcomes before tightening runtime capability restrictions.",
        tableTitle: "Policies",
        actionLabel: "Preview enforcement",
        drawerTitle: "Sandbox preview",
        evidenceTitle: "enforcement preview",
      };
    case "container-pool-policies":
      return {
        title: "Container Pool Policies",
        subtitle: "Estimate warm-capacity impact before changing container pool saturation limits.",
        tableTitle: "Container pools",
        actionLabel: "Estimate impact",
        drawerTitle: "Capacity estimate",
        evidenceTitle: "capacity estimate",
      };
  }
});

function primaryValue(row: AdminResource): string {
  return String(row.name || row.provider || row.label || `item-${row.id}`);
}

function secondaryValue(row: AdminResource): string {
  switch (props.kind) {
    case "observability-exporters":
      return `${String(row.exporter_type || "otlp")} -> ${String(row.target_ref_redacted || row.target_ref || "redacted")}`;
    case "semantic-store":
      return `${String(row.embedding_model || "embedding")} / ${String(row.connection_ref || "connection")}`;
    case "sandbox-policies":
      return `${String(row.network_policy || "network")} / ${String(row.filesystem_policy || "filesystem")}`;
    case "container-pool-policies":
      return `max ${String(row.max_containers || 0)} / ${String(row.cpu_limit || "cpu")}`;
  }
}

function summarizeList(value: unknown): string {
  return Array.isArray(value) && value.length > 0 ? value.map((entry) => String(entry)).join(", ") : "none";
}

function summarizeIndexCoverage(value: unknown): string {
  if (!value || typeof value !== "object") return "none";
  return Object.entries(value as Record<string, unknown>)
    .map(([key, coverage]) => `${key} ${String(coverage)}%`)
    .join(", ");
}

function formatRatio(value: unknown): string {
  const ratio = typeof value === "number" ? value : Number(value || 0);
  return `${Math.round(ratio * 100)}%`;
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const response = await listForKind();
    rows.value = response.items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function listForKind() {
  switch (props.kind) {
    case "observability-exporters":
      return consoleClient.listObservabilityExporters();
    case "semantic-store":
      return consoleClient.listSemanticStoreProviders();
    case "sandbox-policies":
      return consoleClient.listSandboxPolicies();
    case "container-pool-policies":
      return consoleClient.listContainerPoolPolicies();
  }
}

async function runAction(row: AdminResource) {
  selected.value = row;
  actionResult.value = null;
  error.value = null;
  try {
    switch (props.kind) {
      case "observability-exporters":
        actionResult.value = await consoleClient.validateObservabilityExporter(Number(row.id), "Validate exporter readiness for controlled rollout.");
        break;
      case "semantic-store":
        actionResult.value = await consoleClient.validateSemanticStoreProvider(Number(row.id), "Validate semantic store provider before enabling retrieval.");
        break;
      case "sandbox-policies":
        actionResult.value = await consoleClient.previewSandboxPolicy(
          Number(row.id),
          { capabilities: ["network", "filesystem"] },
          "Preview sandbox enforcement before policy save.",
        );
        break;
      case "container-pool-policies":
        actionResult.value = await consoleClient.estimateContainerPoolPolicy(
          Number(row.id),
          { requested_workers: 4 },
          "Estimate container pool saturation before policy update.",
        );
        break;
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
}

function closeDrawer() {
  selected.value = null;
  actionResult.value = null;
}

onMounted(load);
</script>

<style scoped>
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
  background: var(--color-surface-muted);
  padding: 12px;
}

.detail-span {
  grid-column: 1 / -1;
}

.detail-grid dt {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.detail-grid dd {
  margin: 0;
}

.evidence-panel {
  display: grid;
  gap: 8px;
}

.json-preview {
  margin: 0;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 86%, transparent);
  padding: 12px;
  overflow: auto;
  font-size: 12px;
}

.muted {
  color: var(--color-text-muted);
}

.mono {
  font-family: var(--font-mono, "SFMono-Regular", Consolas, monospace);
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
