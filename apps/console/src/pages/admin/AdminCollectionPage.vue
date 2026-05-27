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
            <td class="mono muted">{{ item.tenant_id || "-" }}</td>
            <td class="mono muted">{{ item.project_id || "-" }}</td>
            <td class="mono muted">{{ item.environment || "-" }}</td>
            <td>{{ item.created_at || "-" }}</td>
            <td>{{ item.updated_at || "-" }}</td>
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
const mutatingId = ref<string | null>(null);
const error = ref<ConsoleApiError | null>(null);
const items = ref<AdminResource[]>([]);
const createForm = reactive<Record<string, string>>({});

const createFields = computed(() => fieldsForPath(props.resourcePath));
const canWrite = computed(() => auth.can(writePermissionForPath(props.resourcePath)));

async function loadItems() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    items.value = (await consoleClient.listAdminCollection(props.resourcePath)).items;
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
    return { name, id: formValue("id") || undefined, slug: formValue("slug") || name };
  }
  if (props.resourcePath === "/v1/identity/projects") {
    return {
      name,
      tenant_id: formValue("tenant_id") || scope.tenant_id,
      slug: formValue("slug") || name,
    };
  }
  if (props.resourcePath === "/v1/identity/environments") {
    return {
      name,
      tenant_id: formValue("tenant_id") || scope.tenant_id,
      project_id: formValue("project_id") || scope.project_id,
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
  if (props.resourcePath === "/v1/service-accounts" || props.resourcePath === "/v1/identity/roles") {
    return {
      name,
      description: formValue("description"),
      tenant_id: scope.tenant_id,
      project_id: scope.project_id,
    };
  }
  return { name };
}

function formValue(key: string): string {
  return String(createForm[key] || "").trim();
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
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Acme" },
      { key: "id", label: t("id"), placeholder: "tenant_acme" },
      { key: "slug", label: t("slug"), placeholder: "acme" },
    ];
  }
  if (path === "/v1/identity/projects") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Support Platform" },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: scope.tenant_id },
      { key: "slug", label: t("slug"), placeholder: "support-platform" },
    ];
  }
  if (path === "/v1/identity/environments") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Production" },
      { key: "environment", label: t("environment"), required: true, placeholder: "prod" },
      { key: "tenant_id", label: t("tenant"), required: true, defaultValue: scope.tenant_id },
      { key: "project_id", label: t("project"), required: true, defaultValue: scope.project_id },
    ];
  }
  if (path === "/v1/identity/permissions") {
    return [
      { key: "name", label: t("name"), required: true, placeholder: "Read agents" },
      { key: "resource", label: t("resource"), required: true, placeholder: "agent" },
      { key: "action", label: t("action"), required: true, placeholder: "read" },
    ];
  }
  if (path === "/v1/identity/roles" || path === "/v1/service-accounts") {
    return [
      { key: "name", label: t("name"), required: true },
      { key: "description", label: t("description") },
    ];
  }
  return [{ key: "name", label: t("name"), required: true }];
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
