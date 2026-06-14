<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Governance</p>
        <h1 class="page-title">{{ detail?.item.name || `${kindLabel} #${assetId}` }}</h1>
        <p class="page-subtitle">v{{ detail?.item.version || "-" }} · {{ String(detail?.item.status || "draft") }}</p>
      </div>
      <RouterLink class="button" :to="listTo">Back</RouterLink>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="false" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="panel" :lines="10" />
    </section>

    <section v-if="mode !== 'offline' && detail" class="grid cols-2 sections">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Lifecycle</h2>
            <p class="panel-copy">Validate, approve, publish, deprecate, archive, or roll back this version.</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <div class="status-row">
            <StatusBadge :status="badgeStatus" :label="String(detail.item.status)" />
            <span class="muted">validated: {{ detail.validation.validated_at || "never" }}</span>
          </div>
          <label>
            <span>Audit reason</span>
            <input v-model="auditReason" class="input" placeholder="governance change reason" />
          </label>
          <label>
            <span>Rollback target</span>
            <select v-model="rollbackTarget" class="input">
              <option value="">previous version</option>
              <option v-for="entry in rollbackOptions" :key="entry.id" :value="entry.version">
                {{ entry.version }}
              </option>
            </select>
          </label>
          <div class="action-grid">
            <button class="button" type="button" :disabled="mutating" @click="runValidate">Validate</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('approve')">Approve</button>
            <button class="button primary" type="button" :disabled="mutating" @click="runAction('publish')">Publish</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('deprecate')">Deprecate</button>
            <button class="button danger" type="button" :disabled="mutating" @click="runAction('archive')">Archive</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('rollback')">Rollback</button>
          </div>
          <p v-if="actionMessage" class="action-message">{{ actionMessage }}</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Risk and usage</h2>
            <p class="panel-copy">See dependency edges, used-by resources, and validation blockers.</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <div>
            <p class="section-kicker">Asset facts</p>
            <ul class="plain-list">
              <li v-for="fact in assetFacts" :key="fact.label">
                {{ fact.label }} · {{ fact.value }}
              </li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">Risk flags</p>
            <div class="chip-row">
              <span v-for="flag in detail.risk_flags" :key="flag" class="chip">{{ flag }}</span>
              <span v-if="detail.risk_flags.length === 0" class="muted">none</span>
            </div>
          </div>
          <div v-if="runtimeRequirementFacts.length > 0">
            <p class="section-kicker">Runtime requirements</p>
            <ul class="plain-list">
              <li v-for="fact in runtimeRequirementFacts" :key="fact.label">
                {{ fact.label }} · {{ fact.value }}
              </li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">Dependencies</p>
            <ul class="plain-list">
              <li v-for="dependency in detail.dependencies" :key="`${dependency.name}:${dependency.version}`">
                {{ dependency.kind || dependency.asset_kind || "asset" }} · {{ dependency.name }} · {{ dependency.version }}
              </li>
              <li v-if="detail.dependencies.length === 0" class="muted">No declared dependencies.</li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">Used by</p>
            <ul class="plain-list">
              <li v-for="usage in detail.used_by" :key="`${usage.resource_kind}-${usage.resource_id}`">
                {{ usage.resource_kind }} #{{ usage.resource_id }} · {{ usage.status }} · {{ usage.environment || "shared" }}
              </li>
              <li v-if="detail.used_by.length === 0" class="muted">No scoped references detected.</li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">Validation issues</p>
            <ul class="plain-list">
              <li v-for="issue in detail.validation.issues || []" :key="`${issue.code}-${issue.field}`">
                {{ issue.code }} · {{ issue.field }} · {{ issue.message }}
              </li>
              <li v-if="(detail.validation.issues || []).length === 0" class="muted">No validation issues.</li>
            </ul>
          </div>
        </div>
      </section>
    </section>

    <section v-if="detail" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Version history</h2>
          <p class="panel-copy">Open the diff page to inspect the current version against its previous sibling.</p>
        </div>
        <RouterLink class="button" :to="diffTo">Open diff</RouterLink>
      </div>
      <div class="panel-body">
        <DataTable :columns="historyColumns" :rows="detail.version_history" row-key="id" label="Version history">
          <template #cell-version="{ row }">
            <span class="mono">{{ row.version }}</span>
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :status="row.version === detail.item.version ? badgeStatus : 'neutral'" :label="String(row.status)" />
          </template>
          <template #cell-actions="{ row }">
            <RouterLink class="button" :to="detailRoute(Number(row.id))">Open</RouterLink>
          </template>
        </DataTable>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { AssetCatalogKind, AssetDetail } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DataTable from "../../components/DataTable.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const props = defineProps<{
  kind: AssetCatalogKind;
  assetId: number;
  listRouteName: string;
  detailRouteName: string;
  diffRouteName: string;
}>();

const router = useRouter();
const mode = apiMode();
const loading = ref(false);
const mutating = ref(false);
const error = ref<ConsoleApiError | null>(null);
const detail = ref<AssetDetail | null>(null);
const auditReason = ref("govern asset lifecycle");
const rollbackTarget = ref("");
const actionMessage = ref("");

const historyColumns = [
  { key: "version", label: "Version" },
  { key: "status", label: "Status" },
  { key: "actions", label: "Actions" },
];

const kindLabel = computed(() => ({
  catalog: "Catalog item",
  prompt: "Prompt asset",
  config: "Config asset",
  template: "Template asset",
})[props.kind]);

const badgeStatus = computed(() => {
  const status = String(detail.value?.item.status || "draft");
  if (status === "published") return "ready";
  if (status === "approved" || status === "validated") return "running";
  if (status === "deprecated" || status === "archived") return "disabled";
  return "neutral";
});

const rollbackOptions = computed(() =>
  (detail.value?.version_history || []).filter((entry) => entry.id !== detail.value?.item.id),
);

const assetFacts = computed(() => {
  if (!detail.value) return [];
  const item = detail.value.item;
  const facts = [
    { label: "Kind", value: props.kind },
    { label: "Shape", value: stringValue(item.type) },
    { label: "Provider", value: stringValue(item.provider) },
    { label: "Risk level", value: stringValue(item.risk_level) },
    { label: "Visibility", value: stringValue(item.visibility_level) },
    { label: "Environment", value: stringValue(item.environment) },
    { label: "Content ref", value: stringValue(item.content_ref) },
  ];
  return facts.filter((entry) => entry.value !== "-");
});

const runtimeRequirementFacts = computed(() => {
  if (!detail.value || !isRecord(detail.value.item.runtime_requirements)) return [];
  return Object.entries(detail.value.item.runtime_requirements)
    .map(([label, value]) => ({ label, value: formatFactValue(value) }))
    .filter((entry) => entry.value !== "-");
});

const listTo = computed(() => ({ name: props.listRouteName }));
const diffTo = computed(() => ({ name: props.diffRouteName, params: { assetId: props.assetId } }));

function detailRoute(assetId: number) {
  return { name: props.detailRouteName, params: { assetId } };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "-";
}

function formatFactValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.map((entry) => formatFactValue(entry)).join(", ");
  if (isRecord(value)) return JSON.stringify(value);
  return String(value);
}

async function loadDetail() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    detail.value = await consoleClient.getGovernedAssetDetail(props.kind, props.assetId);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function runValidate() {
  if (mutating.value) return;
  mutating.value = true;
  actionMessage.value = "";
  try {
    const response = await consoleClient.validateGovernedAsset(props.kind, props.assetId, auditReason.value);
    actionMessage.value = `validation ${response.validation?.status || "completed"}`;
    await loadDetail();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    mutating.value = false;
  }
}

async function runAction(action: "approve" | "publish" | "deprecate" | "archive" | "rollback") {
  if (mutating.value) return;
  mutating.value = true;
  actionMessage.value = "";
  try {
    const payload: Record<string, unknown> = { audit_reason: auditReason.value };
    if (action === "rollback" && rollbackTarget.value) {
      payload.target_version = rollbackTarget.value;
    }
    const response = await consoleClient.mutateGovernedAsset(props.kind, props.assetId, action, payload);
    actionMessage.value = `${action} -> ${String(response.item.status)}`;
    if (response.item.id !== props.assetId) {
      await router.replace({ name: props.detailRouteName, params: { assetId: response.item.id } });
      return;
    }
    await loadDetail();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    mutating.value = false;
  }
}

onMounted(() => {
  void loadDetail();
});
</script>

<style scoped>
.status-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.action-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}

.chip-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  font-size: 0.85rem;
}

.plain-list {
  margin: 0;
  padding-left: 18px;
}
</style>
