<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ labelFor(kicker) }}</p>
        <h1 class="page-title">{{ labelFor(title) }}</h1>
        <p class="page-subtitle">{{ props.description || t("adminCollectionCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canWrite" @click="openCreateDrawer">
        {{ t("create") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && items.length === 0" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="table" :lines="8" />
    </section>

    <DataTable
      v-if="mode !== 'offline' && !loading && !error && items.length > 0"
      :columns="tableColumns"
      :rows="items"
      row-key="id"
      :label="labelFor(title)"
    >
      <template #cell-id="{ row }">
        <span class="mono">{{ row.id }}</span>
      </template>
      <template #cell-name="{ row }">
        <input
          class="input compact-input"
          :value="String(row.name || row.label || '')"
          :placeholder="t('name')"
          :disabled="!canWrite"
          @change="updateName(row, ($event.target as HTMLInputElement).value)"
        />
      </template>
      <template #cell-status="{ row }">
        <StatusBadge :status="String(row.status || 'active')" :label="String(row.status || 'active')" />
      </template>
      <template #cell-tenant="{ row }">
        <span class="muted">{{ tenantName(row.tenant_id) }}</span>
      </template>
      <template #cell-project="{ row }">
        <span class="muted">{{ projectName(row.project_id) }}</span>
      </template>
      <template #cell-environment="{ row }">
        <span class="mono muted">{{ row.environment || "-" }}</span>
      </template>
      <template #cell-createdAt="{ row }">
        {{ formatDateTime(row.created_at) }}
      </template>
      <template #cell-updatedAt="{ row }">
        {{ formatDateTime(row.updated_at) }}
      </template>
      <template #cell-metadata="{ row }">
        <span class="mono muted">{{ metadataPreview(row) }}</span>
      </template>
      <template #cell-actions="{ row }">
        <div class="row-actions">
          <button class="button" type="button" @click="openDetailDrawer(row)">
            {{ t("view") }}
          </button>
          <button class="button" type="button" :disabled="mutatingId === row.id || !canWrite" @click="openEditDrawer(row)">
            {{ t("edit") }}
          </button>
          <button class="button" type="button" :disabled="mutatingId === row.id || !canWrite" @click="toggleStatus(row)">
            {{ row.status === "disabled" ? t("enable") : t("disable") }}
          </button>
          <button class="button danger" type="button" :disabled="mutatingId === row.id || !canWrite" @click="openDeleteConfirm(row)">
            {{ t("delete") }}
          </button>
        </div>
      </template>
    </DataTable>

    <AppDrawer
      :open="showCreate"
      :label="t('create')"
      :title="`${t('create')} ${labelFor(title)}`"
      :kicker="labelFor(kicker)"
      @close="closeCreateDrawer"
    >
      <form class="drawer-form" @submit.prevent="createItem">
            <label v-for="field in createFields" :key="field.key" class="field">
              {{ field.label }}
              <input
                v-model="createForm[field.key]"
                class="input"
                :required="field.required"
                :placeholder="field.placeholder"
              />
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeCreateDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creating">
                {{ creating ? t("creating") : t("save") }}
              </button>
            </div>
      </form>
    </AppDrawer>

    <AppDrawer
      :open="Boolean(detailItem)"
      :label="t('details')"
      :title="detailItem ? `${t('details')} #${detailItem.id}` : t('details')"
      :kicker="labelFor(kicker)"
      width="wide"
      @close="closeDetailDrawer"
    >
      <div class="drawer-form">
            <pre class="json-preview">{{ formatJson(detailItem) }}</pre>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeDetailDrawer">{{ t("cancel") }}</button>
            </div>
      </div>
    </AppDrawer>

    <AppDrawer
      :open="Boolean(editItem)"
      :label="t('edit')"
      :title="editItem ? `${t('edit')} #${editItem.id}` : t('edit')"
      :kicker="labelFor(kicker)"
      width="wide"
      @close="closeEditDrawer"
    >
      <form class="drawer-form" @submit.prevent="saveEditDrawer">
            <label class="field">
              {{ t("payload") }}
              <textarea v-model="editPayloadJson" class="textarea code-input" rows="18"></textarea>
            </label>
            <p v-if="editError" class="form-error">{{ editError }}</p>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeEditDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="mutatingId === editItem?.id">
                {{ mutatingId === editItem?.id ? t("saving") : t("save") }}
              </button>
            </div>
      </form>
    </AppDrawer>

    <DangerConfirmDialog
      :open="Boolean(deleteTarget)"
      :title="t('confirmDelete')"
      :message="t('confirmDeleteCopy')"
      :items="deleteConfirmItems"
      :confirm-label="t('delete')"
      :cancel-label="t('cancel')"
      :busy-label="t('saving')"
      :busy="Boolean(deleteTarget && mutatingId === deleteTarget.id)"
      :error="deleteError"
      @cancel="closeDeleteConfirm"
      @confirm="runConfirmedDelete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import DataTable from "../../components/DataTable.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";
import { formatDateTime } from "../../utils/dateTime";

const props = defineProps<{
  title: string;
  kicker: string;
  description: string;
  resourcePath: string;
  seedName: string;
}>();

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const loading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const mutatingId = ref<number | null>(null);
const error = ref<ConsoleApiError | null>(null);
const items = ref<AdminResource[]>([]);
const tenantOptions = ref<AdminResource[]>([]);
const projectOptions = ref<AdminResource[]>([]);
const detailItem = ref<AdminResource | null>(null);
const editItem = ref<AdminResource | null>(null);
const deleteTarget = ref<AdminResource | null>(null);
const deleteError = ref<ConsoleApiError | null>(null);
const editPayloadJson = ref("{}");
const editError = ref("");
const createForm = reactive<Record<string, string>>({});

const createFields = computed(() => fieldsForPath(props.resourcePath));
const canWrite = computed(() => auth.can(writePermissionForPath(props.resourcePath)));
const deleteConfirmItems = computed(() => deleteTarget.value ? [
  { label: t("id"), value: String(deleteTarget.value.id) },
  { label: t("name"), value: String(deleteTarget.value.name || deleteTarget.value.label || "-") },
  { label: t("status"), value: String(deleteTarget.value.status || "-") },
] : []);
const tableColumns = computed(() => [
  { key: "id", label: t("id") },
  { key: "name", label: t("name") },
  { key: "status", label: t("status") },
  { key: "tenant", label: t("tenant") },
  { key: "project", label: t("project") },
  { key: "environment", label: t("environment") },
  { key: "createdAt", label: t("createdAt") },
  { key: "updatedAt", label: t("updatedAt") },
  { key: "metadata", label: t("metadata") },
  { key: "actions", label: t("actions") },
]);

async function loadItems() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    items.value = (await consoleClient.listAdminCollection(props.resourcePath)).items;
    await loadScopeLabels();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createItem() {
  if (mode === "offline" || !canWrite.value) return;
  creating.value = true;
  error.value = null;
  try {
    const item = await consoleClient.createAdminItem(props.resourcePath, {
      ...newItemPayloadFromForm(),
      metadata: { created_by: "console" },
    });
    items.value = [item, ...items.value];
    closeCreateDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function openCreateDrawer() {
  if (!canWrite.value) return;
  resetCreateForm();
  showCreate.value = true;
}

function closeCreateDrawer() {
  showCreate.value = false;
  resetCreateForm();
}

function openDetailDrawer(item: AdminResource) {
  detailItem.value = item;
}

function closeDetailDrawer() {
  detailItem.value = null;
}

function openEditDrawer(item: AdminResource) {
  if (!canWrite.value) return;
  editItem.value = item;
  editError.value = "";
  editPayloadJson.value = JSON.stringify(editPayloadForItem(item), null, 2);
}

function closeEditDrawer() {
  editItem.value = null;
  editError.value = "";
  editPayloadJson.value = "{}";
}

async function saveEditDrawer() {
  if (!editItem.value || mode === "offline" || !canWrite.value) return;
  const payload = parseEditPayload();
  if (!payload) return;
  await updateItem(editItem.value, payload);
  if (!error.value) closeEditDrawer();
}

function parseEditPayload(): Record<string, unknown> | null {
  editError.value = "";
  try {
    const parsed = JSON.parse(editPayloadJson.value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      editError.value = t("jsonObjectRequired");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    editError.value = t("invalidJson");
    return null;
  }
}

function editPayloadForItem(item: AdminResource): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(item)) {
    if (["id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by", "is_deleted"].includes(key)) continue;
    payload[key] = value;
  }
  return payload;
}

async function updateName(item: AdminResource, name: string) {
  if (mode === "offline" || !canWrite.value || !name || name === item.name) return;
  await updateItem(item, { name });
}

async function toggleStatus(item: AdminResource) {
  if (!canWrite.value) return;
  await updateItem(item, { status: item.status === "disabled" ? "active" : "disabled" });
}

function openDeleteConfirm(item: AdminResource) {
  if (!canWrite.value) return;
  deleteTarget.value = item;
  deleteError.value = null;
}

function closeDeleteConfirm() {
  if (deleteTarget.value && mutatingId.value === deleteTarget.value.id) return;
  deleteTarget.value = null;
  deleteError.value = null;
}

async function runConfirmedDelete() {
  if (!deleteTarget.value || mode === "offline" || !canWrite.value) return;
  mutatingId.value = deleteTarget.value.id;
  deleteError.value = null;
  try {
    const deleted = await consoleClient.deleteAdminItem(props.resourcePath, deleteTarget.value.id);
    replaceItem(deleted);
    deleteTarget.value = null;
  } catch (caught) {
    deleteError.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
}

async function updateItem(item: AdminResource, payload: Record<string, unknown>) {
  if (mode === "offline") return;
  mutatingId.value = item.id;
  error.value = null;
  try {
    const updated = await consoleClient.updateAdminItem(props.resourcePath, item.id, payload);
    replaceItem(updated);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
}

function replaceItem(next: AdminResource) {
  items.value = items.value.map((item) => (item.id === next.id ? next : item));
}

function newItemPayloadFromForm(): Record<string, unknown> {
  const scope = readCurrentScope();
  const name = formValue("name");
  if (props.resourcePath === "/v1/identity/tenants") {
    const slug = slugify(name);
    return { name, slug: slug || undefined };
  }
  if (props.resourcePath === "/v1/identity/projects") {
    const slug = slugify(name);
    return {
      name,
      tenant_id: numericId(formValue("tenant_id") || String(scope.tenant_id)),
      slug: slug || undefined,
    };
  }
  if (props.resourcePath === "/v1/identity/environments") {
    return {
      name,
      tenant_id: numericId(formValue("tenant_id") || String(scope.tenant_id)),
      project_id: numericId(formValue("project_id") || String(scope.project_id)),
      environment: formValue("environment") || name,
    };
  }
  if (props.resourcePath === "/v1/identity/permissions") {
    return {
      name,
      resource: formValue("resource"),
      action: formValue("action"),
      tenant_id: scope.tenant_id,
      project_id: scope.project_id,
    };
  }
  if (props.resourcePath === "/v1/identity/roles") {
    return {
      name,
      description: formValue("description"),
      tenant_id: scope.tenant_id,
      project_id: scope.project_id,
    };
  }
  const payload: Record<string, unknown> = {};
  for (const field of createFields.value) {
    const value = formValue(field.key);
    if (!value) continue;
    payload[field.key] = parseFieldValue(field.key, value);
  }
  if (name && !payload.name) payload.name = name;
  return payload;
}

function formValue(key: string): string {
  return String(createForm[key] || "").trim();
}

function numericId(value: string): number {
  return Number(value);
}

function resetCreateForm() {
  for (const key of Object.keys(createForm)) {
    delete createForm[key];
  }
  for (const field of createFields.value) {
    createForm[field.key] = field.defaultValue || "";
  }
}

function writePermissionForPath(path: string): string {
  if (path.includes("/identity/operators")) return "identity:operator:write";
  if (path.includes("/identity/roles")) return "identity:role:write";
  if (path.includes("/identity/permissions")) return "identity:permission:write";
  if (path.includes("/identity/tenants") || path.includes("/identity/projects") || path.includes("/identity/environments")) {
    return "identity:scope:write";
  }
  return "admin:write";
}

function fieldsForPath(path: string): Array<{
  key: string;
  label: string;
  required?: boolean;
  placeholder?: string;
  defaultValue?: string;
}> {
  const scope = readCurrentScope();
  if (path === "/v1/identity/tenants") {
    return [{ key: "name", label: t("name"), required: true, placeholder: t("tenantNamePlaceholder") }];
  }
  if (path === "/v1/identity/projects") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: t("supportPlatformPlaceholder") },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: String(scope.tenant_id) },
    ];
  }
  if (path === "/v1/identity/environments") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: t("productionNamePlaceholder") },
      { key: "environment", label: t("environment"), required: true, placeholder: t("productionEnvPlaceholder") },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: String(scope.tenant_id) },
      { key: "project_id", label: t("project"), required: true, defaultValue: String(scope.project_id) },
    ];
  }
  if (path === "/v1/identity/permissions") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: t("readAgentsPlaceholder") },
      { key: "resource", label: t("resource"), required: true, placeholder: "agent" },
      { key: "action", label: t("action"), required: true, placeholder: "read" },
    ];
  }
  if (path === "/v1/identity/roles") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "description", label: t("description") },
    ];
  }
  if (path === "/v1/published-surfaces") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: t("publicApiPlaceholder") },
      { key: "deployment_id", label: t("deploymentIdLabel"), required: true, placeholder: "1" },
      { key: "type", label: t("type"), defaultValue: "http" },
    ];
  }
  if (path === "/v1/ingress-routes") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: t("publicRoutePlaceholder") },
      { key: "surface_id", label: t("surfaceIdLabel"), required: true, placeholder: "1" },
      { key: "path", label: t("path"), required: true, placeholder: "/api/support" },
      { key: "auth_mode", label: t("authMode"), defaultValue: "api_key" },
    ];
  }
  if (path === "/v1/artifacts") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "artifact_type", label: t("artifactType"), defaultValue: "file" },
      { key: "mime_type", label: t("mimeType"), defaultValue: "application/octet-stream" },
      { key: "storage_uri", label: t("storageUri"), required: true, placeholder: "minio://bucket/key" },
      { key: "checksum", label: t("checksum"), required: true },
      { key: "size_bytes", label: t("sizeBytes"), defaultValue: "0" },
      { key: "run_id", label: t("runId") },
    ];
  }
  if (path === "/v1/dataset-items") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "dataset_id", label: t("datasetId"), required: true, placeholder: "1" },
      { key: "input_ref", label: t("inputRef"), required: true },
      { key: "output_ref", label: t("outputRef") },
      { key: "expected_ref", label: t("expectedRef") },
    ];
  }
  if (path === "/v1/experiments") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "agent_id", label: t("agentId"), required: true },
      { key: "candidate_agent_version_id", label: t("candidateVersionId"), required: true },
      { key: "dataset_id", label: t("datasetId"), required: true },
      { key: "baseline_agent_version_id", label: t("baselineVersionId") },
    ];
  }
  if (path === "/v1/evaluations/results") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "experiment_run_id", label: t("experimentRunId"), required: true },
      { key: "evaluator_name", label: t("evaluator"), required: true },
      { key: "score", label: t("score"), required: true, defaultValue: "1" },
      { key: "passed", label: t("passed"), required: true, defaultValue: "true" },
    ];
  }
  if (path === "/v1/feedback") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "run_id", label: t("runId"), required: true },
      { key: "source", label: t("source"), defaultValue: "console" },
      { key: "rating", label: t("rating") },
      { key: "comment", label: t("comment") },
    ];
  }
  if (path === "/v1/replay-jobs") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "source_run_id", label: t("sourceRunId"), required: true },
      { key: "candidate_agent_version_id", label: t("candidateVersionId"), required: true },
      { key: "source_agent_version_id", label: t("sourceVersionId") },
    ];
  }
  if (path === "/v1/alerts/rules") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "channel_id", label: t("channelId"), required: true, placeholder: "1" },
      { key: "signal", label: t("signal"), defaultValue: "runtime.error_rate" },
      { key: "threshold", label: t("threshold"), defaultValue: "1" },
    ];
  }
  if (path === "/v1/observability/exporters") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "exporter_type", label: t("exporterType"), defaultValue: "otlp" },
      { key: "target_ref", label: t("targetRef"), required: true, placeholder: "http://otel:4318" },
    ];
  }
  if (path === "/v1/sandbox/policies") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "isolation_level", label: t("isolation"), defaultValue: "process" },
      { key: "network_policy", label: t("network"), defaultValue: "deny_all" },
      { key: "filesystem_policy", label: t("filesystem"), defaultValue: "read_only" },
    ];
  }
  if (path === "/v1/container-pool/policies") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "max_containers", label: t("maxContainers"), defaultValue: "10" },
      { key: "cpu_limit", label: t("cpuLimit"), defaultValue: "1000m" },
      { key: "memory_limit", label: t("memoryLimit"), defaultValue: "1Gi" },
      { key: "idle_timeout_seconds", label: t("idleTimeoutSeconds"), defaultValue: "300" },
    ];
  }
  return [{ key: "name", label: t("name"), required: true }];
}

function parseFieldValue(key: string, value: string): unknown {
  if (["size_bytes", "threshold", "score", "max_containers", "idle_timeout_seconds"].includes(key)) return Number(value);
  if (key.endsWith("_id")) return Number(value);
  if (key === "passed" || key === "access_log_enabled") {
    return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  }
  return value;
}

async function loadScopeLabels() {
  if (mode === "offline") return;
  const hasTenantColumn = items.value.some((item) => item.tenant_id !== undefined && item.tenant_id !== null);
  const hasProjectColumn = items.value.some((item) => item.project_id !== undefined && item.project_id !== null);
  if (!hasTenantColumn && !hasProjectColumn) {
    tenantOptions.value = [];
    projectOptions.value = [];
    return;
  }
  tenantOptions.value = (await consoleClient.listAdminCollection("/v1/identity/tenants")).items;
  if (!hasProjectColumn) {
    projectOptions.value = [];
    return;
  }
  const projectPages = await Promise.all(
    tenantOptions.value.map((tenant) =>
      consoleClient.listAdminCollection("/v1/identity/projects", {
        tenant_id: Number(tenant.id),
      }),
    ),
  );
  projectOptions.value = projectPages.flatMap((page) => page.items);
}

function tenantName(value: unknown): string {
  return relatedName(tenantOptions.value, value);
}

function projectName(value: unknown): string {
  return relatedName(projectOptions.value, value);
}

function relatedName(options: AdminResource[], value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  const match = options.find((item) => String(item.id) === String(value));
  return match ? String(match.name || match.slug || match.environment || `#${match.id}`) : `#${String(value)}`;
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function metadataPreview(item: AdminResource): string {
  const metadata = item.metadata;
  if (!metadata || typeof metadata !== "object") return "-";
  return JSON.stringify(metadata);
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function labelFor(value: string): string {
  const key = value.replace(/[^a-zA-Z0-9]+(.)/g, (_, char: string) => char.toUpperCase()).replace(/^./, (char) => char.toLowerCase());
  if (key in {
    identity: true,
    governance: true,
    observability: true,
    enterpriseOps: true,
    settings: true,
    tenants: true,
    projects: true,
    environments: true,
    users: true,
    roles: true,
    permissions: true,
    serviceAccounts: true,
    modelGateways: true,
    tools: true,
    secrets: true,
    catalogItems: true,
    promptAssets: true,
    configAssets: true,
    templateAssets: true,
    auditLogs: true,
    artifacts: true,
    evaluationResults: true,
    datasets: true,
    experiments: true,
    replayJobs: true,
    ingressRoutes: true,
    feedback: true,
    backupPlans: true,
    restoreJobs: true,
    webhookSubscriptions: true,
    notificationChannels: true,
    alertRules: true,
    incidents: true,
    semanticStoreProviders: true,
    observabilityExporters: true,
    sandboxPolicies: true,
    containerPoolPolicies: true,
  }) {
    return t(key as Parameters<typeof t>[0]);
  }
  return value;
}

onMounted(loadItems);
watch(
  () => props.resourcePath,
  () => {
    closeCreateDrawer();
    closeDetailDrawer();
    closeEditDrawer();
    closeDeleteConfirm();
    loadItems();
  },
);
watch(createFields, resetCreateForm, { immediate: true });
</script>

<style scoped>
.field {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.form-actions {
  display: flex;
  align-items: end;
  justify-content: flex-end;
  gap: 8px;
}

.dense-loading {
  display: grid;
  gap: 16px;
}

.drawer-form {
  display: grid;
  align-content: start;
  gap: 14px;
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

.compact-input {
  min-width: 150px;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  white-space: nowrap;
}

.textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  padding: 10px 12px;
  font: inherit;
}

.code-input,
.json-preview {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
}

.json-preview {
  overflow: auto;
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 50%, transparent);
  padding: 12px;
}

.form-error {
  margin: 0;
  color: var(--color-danger);
  font-weight: 700;
}
</style>
