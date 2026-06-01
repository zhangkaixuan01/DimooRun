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

    <div v-if="mode !== 'offline' && !loading && !error && items.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("id") }}</th>
            <th>{{ t("name") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("tenant") }}</th>
            <th>{{ t("project") }}</th>
            <th>{{ t("environment") }}</th>
            <th>{{ t("createdAt") }}</th>
            <th>{{ t("updatedAt") }}</th>
            <th>{{ t("metadata") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td class="mono">{{ item.id }}</td>
            <td>
              <input
                class="input compact-input"
                :value="String(item.name || item.label || '')"
                :placeholder="t('name')"
                :disabled="!canWrite"
                @change="updateName(item, ($event.target as HTMLInputElement).value)"
              />
            </td>
            <td><StatusBadge :status="String(item.status || 'active')" :label="String(item.status || 'active')" /></td>
            <td class="muted">{{ tenantName(item.tenant_id) }}</td>
            <td class="muted">{{ projectName(item.project_id) }}</td>
            <td class="mono muted">{{ item.environment || "-" }}</td>
            <td>{{ formatDateTime(item.created_at) }}</td>
            <td>{{ formatDateTime(item.updated_at) }}</td>
            <td class="mono muted">{{ metadataPreview(item) }}</td>
            <td>
              <div class="row-actions">
                <button class="button" type="button" :disabled="mutatingId === item.id || !canWrite" @click="toggleStatus(item)">
                  {{ item.status === "disabled" ? t("enable") : t("disable") }}
                </button>
                <button class="button danger" type="button" :disabled="mutatingId === item.id || !canWrite" @click="deleteItem(item)">
                  {{ t("delete") }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="showCreate" class="drawer-layer" @click.self="closeCreateDrawer">
        <aside class="drawer" :aria-label="t('create')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ labelFor(kicker) }}</p>
              <h2>{{ t("create") }} {{ labelFor(title) }}</h2>
            </div>
            <button class="button" type="button" @click="closeCreateDrawer">{{ t("cancel") }}</button>
          </header>
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
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
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
const createForm = reactive<Record<string, string>>({});

const createFields = computed(() => fieldsForPath(props.resourcePath));
const canWrite = computed(() => auth.can(writePermissionForPath(props.resourcePath)));

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

async function updateName(item: AdminResource, name: string) {
  if (mode === "offline" || !canWrite.value || !name || name === item.name) return;
  await updateItem(item, { name });
}

async function toggleStatus(item: AdminResource) {
  if (!canWrite.value) return;
  await updateItem(item, { status: item.status === "disabled" ? "active" : "disabled" });
}

async function deleteItem(item: AdminResource) {
  if (mode === "offline" || !canWrite.value) return;
  mutatingId.value = item.id;
  error.value = null;
  try {
    const deleted = await consoleClient.deleteAdminItem(props.resourcePath, item.id);
    replaceItem(deleted);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
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
    return [{ key: "name", label: t("name"), required: true, placeholder: "Acme" }];
  }
  if (path === "/v1/identity/projects") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Support Platform" },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: String(scope.tenant_id) },
    ];
  }
  if (path === "/v1/identity/environments") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Production" },
      { key: "environment", label: t("environment"), required: true, placeholder: "prod" },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: String(scope.tenant_id) },
      { key: "project_id", label: t("project"), required: true, defaultValue: String(scope.project_id) },
    ];
  }
  if (path === "/v1/identity/permissions") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Read agents" },
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
      { key: "name", label: t("name"), required: true, placeholder: "Public API" },
      { key: "deployment_id", label: "Deployment ID", required: true, placeholder: "1" },
      { key: "type", label: "Type", defaultValue: "http" },
    ];
  }
  if (path === "/v1/ingress-routes") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Public route" },
      { key: "surface_id", label: "Surface ID", required: true, placeholder: "1" },
      { key: "path", label: "Path", required: true, placeholder: "/api/support" },
      { key: "auth_mode", label: "Auth mode", defaultValue: "api_key" },
    ];
  }
  if (path === "/v1/artifacts") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "artifact_type", label: "Artifact type", defaultValue: "file" },
      { key: "mime_type", label: "MIME type", defaultValue: "application/octet-stream" },
      { key: "storage_uri", label: "Storage URI", required: true, placeholder: "minio://bucket/key" },
      { key: "checksum", label: "Checksum", required: true },
      { key: "size_bytes", label: "Size bytes", defaultValue: "0" },
      { key: "run_id", label: "Run ID" },
    ];
  }
  if (path === "/v1/dataset-items") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "dataset_id", label: "Dataset ID", required: true, placeholder: "1" },
      { key: "input_ref", label: "Input ref", required: true },
      { key: "output_ref", label: "Output ref" },
      { key: "expected_ref", label: "Expected ref" },
    ];
  }
  if (path === "/v1/experiments") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "agent_id", label: "Agent ID", required: true },
      { key: "candidate_agent_version_id", label: "Candidate version ID", required: true },
      { key: "dataset_id", label: "Dataset ID", required: true },
      { key: "baseline_agent_version_id", label: "Baseline version ID" },
    ];
  }
  if (path === "/v1/evaluations/results") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "experiment_run_id", label: "Experiment run ID", required: true },
      { key: "evaluator_name", label: "Evaluator", required: true },
      { key: "score", label: "Score", required: true, defaultValue: "1" },
      { key: "passed", label: "Passed", required: true, defaultValue: "true" },
    ];
  }
  if (path === "/v1/feedback") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "run_id", label: "Run ID", required: true },
      { key: "source", label: "Source", defaultValue: "console" },
      { key: "rating", label: "Rating" },
      { key: "comment", label: "Comment" },
    ];
  }
  if (path === "/v1/replay-jobs") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "source_run_id", label: "Source run ID", required: true },
      { key: "candidate_agent_version_id", label: "Candidate version ID", required: true },
      { key: "source_agent_version_id", label: "Source version ID" },
    ];
  }
  if (path === "/v1/alerts/rules") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "channel_id", label: "Channel ID", required: true, placeholder: "1" },
      { key: "signal", label: "Signal", defaultValue: "runtime.error_rate" },
      { key: "threshold", label: "Threshold", defaultValue: "1" },
    ];
  }
  if (path === "/v1/observability/exporters") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "exporter_type", label: "Exporter type", defaultValue: "otlp" },
      { key: "target_ref", label: "Target ref", required: true, placeholder: "http://otel:4318" },
    ];
  }
  if (path === "/v1/sandbox/policies") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "isolation_level", label: "Isolation", defaultValue: "process" },
      { key: "network_policy", label: "Network", defaultValue: "deny_all" },
      { key: "filesystem_policy", label: "Filesystem", defaultValue: "read_only" },
    ];
  }
  if (path === "/v1/container-pool/policies") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "max_containers", label: "Max containers", defaultValue: "10" },
      { key: "cpu_limit", label: "CPU limit", defaultValue: "1000m" },
      { key: "memory_limit", label: "Memory limit", defaultValue: "1Gi" },
      { key: "idle_timeout_seconds", label: "Idle timeout seconds", defaultValue: "300" },
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
  width: min(440px, 100%);
  grid-template-rows: auto 1fr;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
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

.compact-input {
  min-width: 150px;
}

.row-actions {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}

@media (max-width: 920px) {
  .drawer {
    width: 100%;
  }
}
</style>
