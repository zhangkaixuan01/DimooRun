<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("governanceArea") }}</p>
        <h1 class="page-title">{{ localizedTitle }}</h1>
        <p class="page-subtitle">{{ localizedDescription }}</p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && items.length === 0" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="table" :lines="8" />
    </section>

    <section v-if="mode !== 'offline' && !loading && !error" class="workbench-grid sections">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">{{ t("inventory") }}</h2>
            <p class="panel-copy">{{ t("assetInventoryCopy") }}</p>
          </div>
        </div>
        <div class="panel-body">
          <DataTable :columns="columns" :rows="items" row-key="id" :label="localizedTitle">
            <template #cell-name="{ row }">
              <div>
                <strong>{{ String(row.name || "-") }}</strong>
                <div class="mono muted">v{{ String(row.version || "-") }}</div>
              </div>
            </template>
            <template #cell-status="{ row }">
              <StatusBadge :status="badgeStatus(row)" :label="String(row.status || 'draft')" />
            </template>
            <template #cell-shape="{ row }">
              <span class="mono muted">{{ shapeLabel(row) }}</span>
            </template>
            <template #cell-scope="{ row }">
              <span class="mono muted">{{ scopeLabel(row) }}</span>
            </template>
            <template #cell-actions="{ row }">
              <RouterLink class="button" :to="detailTo(Number(row.id))">{{ t("open") }}</RouterLink>
            </template>
          </DataTable>
        </div>
      </section>

      <aside class="workbench-side">
        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">{{ t("createAsset") }}</h2>
              <p class="panel-copy">{{ t("createAssetCopy") }}</p>
            </div>
          </div>
          <div class="panel-body summary-grid">
            <label class="field">
              <span>{{ t("name") }}</span>
              <input v-model="createForm.name" class="input" placeholder="support-prompt" />
            </label>
            <label class="field">
              <span>{{ t("version") }}</span>
              <input v-model="createForm.version" class="input" placeholder="1.0.0" />
            </label>
            <label class="field" v-if="props.kind === 'catalog' || props.kind === 'template'">
              <span>{{ t("type") }}</span>
              <input v-model="createForm.type" class="input" :placeholder="props.kind === 'catalog' ? 'tool' : 'template'" />
            </label>
            <label class="field" v-if="props.kind === 'catalog'">
              <span>{{ t("providerType") }}</span>
              <input v-model="createForm.provider" class="input" placeholder="local" />
            </label>
            <label class="field" v-if="props.kind !== 'catalog'">
              <span>{{ t("contentRef") }}</span>
              <input v-model="createForm.contentRef" class="input" placeholder="inline:content" />
            </label>
            <label class="field" v-if="props.kind === 'config'">
              <span>{{ t("environment") }}</span>
              <input v-model="createForm.environment" class="input" placeholder="production" />
            </label>
            <label class="field">
              <span>{{ t("auditReason") }}</span>
              <input v-model="createForm.auditReason" class="input" :placeholder="t('createAssetCopy')" />
            </label>
            <div class="create-actions">
              <button class="button primary" type="button" :disabled="creating" @click="createAsset">
                {{ t("createAsset") }}
              </button>
            </div>
            <p v-if="actionMessage" class="action-message">{{ actionMessage }}</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">{{ t("statusSummary") }}</h2>
              <p class="panel-copy">{{ t("statusSummaryCopy") }}</p>
            </div>
          </div>
          <div class="panel-body summary-grid">
            <article v-for="item in summaryCards" :key="item.label" class="summary-card">
              <p class="section-kicker">{{ item.label }}</p>
              <strong class="summary-value">{{ item.count }}</strong>
            </article>
          </div>
        </section>
      </aside>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import type { AssetCatalogKind } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DataTable from "../../components/DataTable.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{
  kind: AssetCatalogKind;
  title: string;
  description: string;
  detailRouteName: string;
}>();

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const creating = ref(false);
const error = ref<ConsoleApiError | null>(null);
const items = ref<AdminResource[]>([]);
const actionMessage = ref("");
const createForm = reactive({
  name: "",
  version: "1.0.0",
  type: props.kind === "catalog" ? "tool" : "template",
  provider: "local",
  contentRef: "inline:content",
  environment: "production",
  auditReason: "register governed asset",
});

const columns = [
  { key: "name", label: t("asset") },
  { key: "status", label: t("lifecycle") },
  { key: "shape", label: t("shape") },
  { key: "scope", label: t("scope") },
  { key: "actions", label: t("actions") },
];

const localizedTitle = computed(() => ({
  catalog: t("catalogItems"),
  prompt: t("promptAssets"),
  config: t("configAssets"),
  template: t("templateAssets"),
})[props.kind]);

const localizedDescription = computed(() => ({
  catalog: t("catalogItemsCopy"),
  prompt: t("promptAssetsCopy"),
  config: t("configAssetsCopy"),
  template: t("templateAssetsCopy"),
})[props.kind]);

const summaryCards = computed(() => {
  const counts = new Map<string, number>();
  for (const item of items.value) {
    const status = String(item.status || "draft");
    counts.set(status, (counts.get(status) || 0) + 1);
  }
  return ["draft", "validated", "approved", "published", "deprecated", "archived"].map((label) => ({
    label,
    count: counts.get(label) || 0,
  }));
});

function badgeStatus(item: AdminResource): string {
  const status = String(item.status || "draft");
  if (status === "published") return "ready";
  if (status === "approved" || status === "validated") return "running";
  if (status === "deprecated" || status === "archived") return "disabled";
  return "neutral";
}

function shapeLabel(item: AdminResource): string {
  if (typeof item.type === "string") return item.type;
  if (typeof item.provider === "string") return item.provider;
  return String(item.kind || props.kind);
}

function scopeLabel(item: AdminResource): string {
  if (typeof item.risk_level === "string") return item.risk_level;
  if (typeof item.visibility_level === "string") return item.visibility_level;
  if (typeof item.environment === "string") return item.environment;
  return "-";
}

function detailTo(assetId: number) {
  return { name: props.detailRouteName, params: { assetId } };
}

function createPayload(): Record<string, unknown> {
  if (props.kind === "catalog") {
    return {
      name: createForm.name,
      version: createForm.version,
      type: createForm.type,
      provider: createForm.provider,
      risk_level: "medium",
      schema_json: {},
      capabilities_json: {},
      required_secrets_json: [],
      required_permissions_json: [],
      runtime_requirements_json: {},
      audit_reason: createForm.auditReason,
    };
  }
  if (props.kind === "prompt") {
    return {
      name: createForm.name,
      version: createForm.version,
      content_ref: createForm.contentRef,
      variables_schema_json: {},
      metadata_json: {},
      audit_reason: createForm.auditReason,
    };
  }
  if (props.kind === "config") {
    return {
      name: createForm.name,
      version: createForm.version,
      content_ref: createForm.contentRef,
      schema_json: {},
      environment: createForm.environment,
      metadata_json: {},
      audit_reason: createForm.auditReason,
    };
  }
  return {
    name: createForm.name,
    version: createForm.version,
    type: createForm.type,
    content_ref: createForm.contentRef,
    schema_json: {},
    metadata_json: {},
    audit_reason: createForm.auditReason,
  };
}

async function createAsset() {
  if (creating.value) return;
  creating.value = true;
  actionMessage.value = "";
  error.value = null;
  try {
    const path = {
      catalog: "/v1/catalog/items",
      prompt: "/v1/assets/prompts",
      config: "/v1/assets/configs",
      template: "/v1/assets/templates",
    }[props.kind];
    const created = await consoleClient.createAdminItem(path, createPayload());
    actionMessage.value = `${t("createdAsset")} #${created.id}.`;
    items.value = [created, ...items.value];
    createForm.name = "";
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

async function loadItems() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    items.value = (await consoleClient.listGovernedAssets(props.kind)).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadItems();
});
</script>

<style scoped>
.summary-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}

.field {
  display: grid;
  gap: 6px;
}

.create-actions {
  display: flex;
  align-items: end;
}

.summary-card {
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
}

.summary-value {
  display: block;
  font-size: 1.5rem;
  margin-top: 6px;
}
</style>
