<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("governance") }}</p>
        <h1 class="page-title">{{ detail?.item.name || `${kindLabel} #${assetId}` }}</h1>
        <p class="page-subtitle">v{{ detail?.item.version || "-" }} · {{ String(detail?.item.status || "draft") }}</p>
      </div>
      <RouterLink class="button" :to="listTo">{{ t("back") }}</RouterLink>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="false" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="panel" :lines="10" />
    </section>

    <section v-if="mode !== 'offline' && detail" class="grid cols-2 sections">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">{{ t("lifecycle") }}</h2>
            <p class="panel-copy">{{ t("assetLifecycleCopy") }}</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <div class="status-row">
            <StatusBadge :status="badgeStatus" :label="String(detail.item.status)" />
            <span class="muted">{{ t("validated") }}: {{ detail.validation.validated_at || t("never") }}</span>
          </div>
          <label>
            <span>{{ t("auditReason") }}</span>
            <input v-model="auditReason" class="input" :placeholder="t('auditReason')" />
          </label>
          <label>
            <span>{{ t("rollbackTarget") }}</span>
            <select v-model="rollbackTarget" class="input">
              <option value="">{{ t("previousVersion") }}</option>
              <option v-for="entry in rollbackOptions" :key="entry.id" :value="entry.version">
                {{ entry.version }}
              </option>
            </select>
          </label>
          <div class="action-grid">
            <button class="button" type="button" :disabled="mutating" @click="runValidate">{{ t("validateAsset") }}</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('approve')">{{ t("approve") }}</button>
            <button class="button primary" type="button" :disabled="mutating" @click="runAction('publish')">{{ publishLabel }}</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('deprecate')">{{ t("deprecate") }}</button>
            <button class="button danger" type="button" :disabled="mutating" @click="runAction('archive')">{{ t("archive") }}</button>
            <button class="button" type="button" :disabled="mutating" @click="runAction('rollback')">{{ rollbackLabel }}</button>
          </div>
          <p v-if="actionMessage" class="action-message">{{ actionMessage }}</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">{{ t("riskAndUsage") }}</h2>
            <p class="panel-copy">{{ t("riskAndUsageCopy") }}</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <div>
            <p class="section-kicker">{{ t("assetFacts") }}</p>
            <ul class="plain-list">
              <li v-for="fact in assetFacts" :key="fact.label">
                {{ fact.label }} · {{ fact.value }}
              </li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">{{ t("riskFlags") }}</p>
            <div class="chip-row">
              <span v-for="flag in detail.risk_flags" :key="flag" class="chip">{{ flag }}</span>
              <span v-if="detail.risk_flags.length === 0" class="muted">{{ t("noRiskFlags") }}</span>
            </div>
          </div>
          <div v-if="runtimeRequirementFacts.length > 0">
            <p class="section-kicker">{{ t("runtimeRequirements") }}</p>
            <ul class="plain-list">
              <li v-for="fact in runtimeRequirementFacts" :key="fact.label">
                {{ fact.label }} · {{ fact.value }}
              </li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">{{ t("validationState") }}</p>
            <p class="muted">{{ detail.validation.status || "unknown" }}</p>
          </div>
          <div>
            <p class="section-kicker">{{ t("versionEvidence") }}</p>
            <ul class="plain-list">
              <li>{{ t("currentVersion") }} · {{ detail.item.version }}</li>
              <li>{{ t("validationState") }} · {{ detail.validation.status || "unknown" }}</li>
              <li>{{ t("rollbackTarget") }} · {{ rollbackOptions[0]?.version || t("previousVersion") }}</li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">{{ t("dependencies") }}</p>
            <ul class="plain-list">
              <li v-for="dependency in detail.dependencies" :key="`${dependency.name}:${dependency.version}`">
                {{ dependency.kind || dependency.asset_kind || "asset" }} · {{ dependency.name }} · {{ dependency.version }}
              </li>
              <li v-if="detail.dependencies.length === 0" class="muted">{{ t("noDeclaredDependencies") }}</li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">{{ linkedUsageLabel }}</p>
            <ul class="plain-list">
              <li v-for="usage in detail.used_by" :key="`${usage.resource_kind}-${usage.resource_id}`">
                {{ usage.resource_kind }} #{{ usage.resource_id }} · {{ usage.status }} · {{ usage.environment || "shared" }}
              </li>
              <li v-if="detail.used_by.length === 0" class="muted">{{ t("noScopedReferences") }}</li>
            </ul>
          </div>
          <div>
            <p class="section-kicker">{{ t("validationIssues") }}</p>
            <ul class="plain-list">
              <li v-for="issue in detail.validation.issues || []" :key="`${issue.code}-${issue.field}`">
                {{ issue.code }} · {{ issue.field }} · {{ issue.message }}
              </li>
              <li v-if="(detail.validation.issues || []).length === 0" class="muted">{{ t("noValidationIssues") }}</li>
            </ul>
          </div>
        </div>
      </section>
    </section>

    <section v-if="detail" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("versionHistory") }}</h2>
          <p class="panel-copy">{{ t("versionHistoryCopy") }}</p>
        </div>
        <RouterLink class="button" :to="diffTo">{{ t("openDiff") }}</RouterLink>
      </div>
      <div class="panel-body">
        <DataTable :columns="historyColumns" :rows="detail.version_history" row-key="id" :label="t('versionHistory')">
          <template #cell-version="{ row }">
            <span class="mono">{{ row.version }}</span>
          </template>
          <template #cell-status="{ row }">
            <StatusBadge :status="row.version === detail.item.version ? badgeStatus : 'neutral'" :label="String(row.status)" />
          </template>
          <template #cell-actions="{ row }">
            <RouterLink class="button" :to="detailRoute(Number(row.id))">{{ t("open") }}</RouterLink>
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
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{
  kind: AssetCatalogKind;
  assetId: number;
  listRouteName: string;
  detailRouteName: string;
  diffRouteName: string;
}>();

const router = useRouter();
const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const mutating = ref(false);
const error = ref<ConsoleApiError | null>(null);
const detail = ref<AssetDetail | null>(null);
const auditReason = ref("govern asset lifecycle");
const rollbackTarget = ref("");
const actionMessage = ref("");

const historyColumns = computed(() => [
  { key: "version", label: t("version") },
  { key: "status", label: t("status") },
  { key: "actions", label: t("actions") },
]);

const kindLabel = computed(() => ({
  catalog: t("catalogItem"),
  prompt: t("promptAsset"),
  config: t("configAsset"),
  template: t("templateAsset"),
})[props.kind]);

const badgeStatus = computed(() => {
  const status = String(detail.value?.item.status || "draft");
  if (status === "published") return "ready";
  if (status === "approved" || status === "validated") return "running";
  if (status === "deprecated" || status === "archived") return "disabled";
  return "neutral";
});
const publishLabel = computed(() => props.kind === "template" || props.kind === "config" ? t("promoteVersion") : t("publish"));
const rollbackLabel = computed(() => props.kind === "template" || props.kind === "config" ? t("rollbackVersion") : t("rollback"));
const linkedUsageLabel = computed(() => props.kind === "config" ? t("linkedDeployments") : props.kind === "template" ? t("linkedCatalogItems") : t("usedBy"));

const rollbackOptions = computed(() =>
  (detail.value?.version_history || []).filter((entry) => entry.id !== detail.value?.item.id),
);

const assetFacts = computed(() => {
  if (!detail.value) return [];
  const item = detail.value.item;
  const facts = [
    { label: t("kind"), value: props.kind },
    { label: t("shape"), value: stringValue(item.type) },
    { label: t("provider"), value: stringValue(item.provider) },
    { label: t("riskLevel"), value: stringValue(item.risk_level) },
    { label: t("visibility"), value: stringValue(item.visibility_level) },
    { label: t("environment"), value: stringValue(item.environment) },
    { label: t("contentRefLabel"), value: stringValue(item.content_ref) },
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
    actionMessage.value = `${t("validationCompleted")}: ${response.validation?.status || "completed"}`;
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
    actionMessage.value = `${t("assetActionCompleted")}: ${action} -> ${String(response.item.status)}`;
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
