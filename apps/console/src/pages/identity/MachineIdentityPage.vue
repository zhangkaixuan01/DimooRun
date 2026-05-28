<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("machineIdentity") }}</h1>
        <p class="page-subtitle">{{ t("machineIdentityCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canWriteServiceAccount" @click="openServiceAccountDrawer">
        {{ t("create") }} {{ t("serviceAccounts") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && serviceAccounts.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error" class="machine-layout">
      <aside class="account-list">
        <button v-for="account in serviceAccounts" :key="account.id" class="account-row" :class="{ active: selectedAccount?.id === account.id }" type="button" @click="selectAccount(account)">
          <strong>{{ account.name }}</strong>
          <span class="mono">{{ account.id }}</span>
          <small>{{ account.status || "active" }} · {{ listValue(account.permissions) }}</small>
        </button>
      </aside>

      <section class="account-detail">
        <header class="detail-header">
          <div>
            <h2>{{ selectedAccount?.name || t("serviceAccounts") }}</h2>
            <p v-if="selectedAccount" class="mono">{{ selectedAccount.tenant_id }} / {{ selectedAccount.project_id || "*" }}</p>
          </div>
          <div class="detail-actions">
            <button class="button" type="button" :disabled="!selectedAccount || !canWriteServiceAccount" @click="openServiceAccountEditDrawer">编辑</button>
            <button class="button danger" type="button" :disabled="!selectedAccount || !canWriteServiceAccount" @click="deleteServiceAccount">{{ t("delete") }}</button>
            <button class="button primary" type="button" :disabled="!selectedAccount || !canWriteApiKey" @click="openKeyDrawer">
              {{ t("createApiKey") }}
            </button>
          </div>
        </header>

        <div v-if="oneTimeKey" class="secret-once">
          <strong>{{ t("oneTimeSecret") }}</strong>
          <code>{{ oneTimeKey }}</code>
        </div>

        <div class="table-wrap embedded">
          <table>
            <thead>
              <tr>
                <th>{{ t("name") }}</th>
                <th>{{ t("scopes") }}</th>
                <th>{{ t("status") }}</th>
                <th>{{ t("lastUsed") }}</th>
                <th>{{ t("actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in apiKeys" :key="key.id">
                <td><strong>{{ key.name }}</strong><br /><span class="mono muted">{{ key.id }}</span></td>
                <td>{{ listValue(key.scopes) }}</td>
                <td><StatusBadge :status="String(key.status || 'active')" :label="String(key.status || 'active')" /></td>
                <td>{{ key.last_used_at || "-" }}</td>
                <td>
                  <button class="button danger" type="button" :disabled="key.status === 'disabled' || !canWriteApiKey" @click="disableKey(key)">
                    {{ t("disable") }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="serviceAccountDrawerOpen" class="drawer-layer" @click.self="closeServiceAccountDrawer">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("machineIdentity") }}</p>
              <h2>{{ serviceAccountDrawerMode === "create" ? t("create") : "编辑" }} {{ t("serviceAccounts") }}</h2>
            </div>
            <button class="button" type="button" @click="closeServiceAccountDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="createServiceAccount">
            <label class="field">
              {{ t("name") }}
              <input v-model="serviceAccountForm.name" class="input" required placeholder="ci-deployer" />
            </label>
            <label class="field">
              {{ t("tenant") }}
              <select v-model="serviceAccountForm.tenant_id" class="select" required :disabled="serviceAccountDrawerMode === 'edit'" @change="onTenantChange">
                <option v-for="tenant in tenantOptions" :key="tenant.id" :value="tenant.id">{{ tenant.name || tenant.id }}</option>
              </select>
            </label>
            <label class="field">
              {{ t("project") }}
              <select v-model="serviceAccountForm.project_id" class="select" required :disabled="serviceAccountDrawerMode === 'edit'">
                <option v-for="project in projectOptions" :key="project.id" :value="project.id">{{ project.name || project.id }}</option>
              </select>
            </label>
            <label class="field">
              {{ t("status") }}
              <select v-model="serviceAccountForm.status" class="select">
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </select>
            </label>
            <fieldset class="permission-fieldset">
              <legend>{{ t("permissions") }}</legend>
              <label v-for="permission in permissionOptions" :key="permission.id" class="permission-row compact">
                <input v-model="serviceAccountForm.permissions" type="checkbox" :value="String(permission.code || permission.name)" />
                <span>
                  <strong class="mono">{{ permission.code || permission.name }}</strong>
                  <small>{{ permission.resource || "-" }} / {{ permission.action || "-" }}</small>
                </span>
              </label>
            </fieldset>
            <InlineApiError :error="mutationError" />
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeServiceAccountDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingServiceAccount">{{ creatingServiceAccount ? t("creating") : t("save") }}</button>
            </div>
          </form>
        </aside>
      </div>

      <div v-if="keyDrawerOpen" class="drawer-layer" @click.self="closeKeyDrawer">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("machineIdentity") }}</p>
              <h2>{{ t("createApiKey") }}</h2>
            </div>
            <button class="button" type="button" @click="closeKeyDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="createApiKey">
            <label class="field">
              {{ t("name") }}
              <input v-model="keyForm.name" class="input" required placeholder="ci-deploy-key" />
            </label>
            <label class="field">
              {{ t("scopes") }}
              <select v-model="keyForm.scopes" class="select" multiple required>
                <option v-for="scope in selectedAccountPermissions" :key="scope" :value="scope">{{ scope }}</option>
              </select>
            </label>
            <label class="field">
              {{ t("expires") }}
              <input v-model="keyForm.expires_at" class="input" type="datetime-local" />
            </label>
            <InlineApiError :error="mutationError" />
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeKeyDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingKey">{{ creatingKey ? t("creating") : t("save") }}</button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <DangerConfirmDialog
      :open="confirmState.open"
      :title="confirmState.title"
      :message="confirmState.message"
      :items="confirmState.items"
      :warning="confirmState.warning"
      :error="mutationError"
      :busy="creatingServiceAccount || creatingKey"
      confirm-label="确认执行"
      @cancel="closeConfirm"
      @confirm="runConfirmedAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const serviceAccounts = ref<AdminResource[]>([]);
const selectedAccount = ref<AdminResource | null>(null);
const apiKeys = ref<AdminResource[]>([]);
const tenantOptions = ref<AdminResource[]>([]);
const projectOptions = ref<AdminResource[]>([]);
const permissionOptions = ref<AdminResource[]>([]);
const loading = ref(false);
const creatingServiceAccount = ref(false);
const creatingKey = ref(false);
const serviceAccountDrawerOpen = ref(false);
const serviceAccountDrawerMode = ref<"create" | "edit">("create");
const keyDrawerOpen = ref(false);
const oneTimeKey = ref("");
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const serviceAccountForm = reactive({ name: "", tenant_id: "", project_id: "", status: "active", permissions: ["agent:read"] as string[] });
const keyForm = reactive({ name: "", scopes: ["agent:read"] as string[], expires_at: "" });
const confirmState = reactive({
  open: false,
  title: "",
  message: "",
  warning: "",
  items: [] as Array<{ label: string; value: string }>,
  action: null as null | (() => Promise<void>),
});
const selectedAccountPermissions = computed(() =>
  Array.isArray(selectedAccount.value?.permissions) ? selectedAccount.value.permissions.map(String) : [],
);
const canWriteServiceAccount = computed(() => auth.can("identity:service-account:write") || auth.can("admin:write"));
const canWriteApiKey = computed(() => auth.can("identity:api-key:write") || auth.can("admin:write"));

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    serviceAccounts.value = (await consoleClient.listServiceAccounts()).items;
    await loadOptions();
    selectedAccount.value = serviceAccounts.value[0] || null;
    if (selectedAccount.value) await loadKeys(selectedAccount.value.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createServiceAccount() {
  if (!canWriteServiceAccount.value) return;
  creatingServiceAccount.value = true;
  mutationError.value = null;
  try {
    const payload = {
      name: serviceAccountForm.name,
      tenant_id: serviceAccountForm.tenant_id,
      project_id: serviceAccountForm.project_id || null,
      permissions: serviceAccountForm.permissions,
      status: serviceAccountForm.status,
    };
    const account =
      serviceAccountDrawerMode.value === "create"
        ? await consoleClient.createServiceAccount(payload)
        : selectedAccount.value
          ? await consoleClient.updateServiceAccount(selectedAccount.value.id, payload)
          : null;
    if (!account) return;
    serviceAccounts.value =
      serviceAccountDrawerMode.value === "create"
        ? [account, ...serviceAccounts.value]
        : serviceAccounts.value.map((item) => (item.id === account.id ? account : item));
    closeServiceAccountDrawer();
    await selectAccount(account);
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    creatingServiceAccount.value = false;
  }
}

async function selectAccount(account: AdminResource) {
  selectedAccount.value = account;
  oneTimeKey.value = "";
  await loadKeys(account.id);
}

async function loadKeys(serviceAccountId: string) {
  apiKeys.value = (await consoleClient.listServiceAccountApiKeys(serviceAccountId)).items;
}

async function createApiKey() {
  if (!selectedAccount.value) return;
  creatingKey.value = true;
  mutationError.value = null;
  try {
    const response = await consoleClient.createServiceAccountApiKey(selectedAccount.value.id, {
      name: keyForm.name,
      scopes: keyForm.scopes,
      expires_at: keyForm.expires_at ? new Date(keyForm.expires_at).toISOString() : null,
    });
    oneTimeKey.value = response.plain_key;
    apiKeys.value = [response.item, ...apiKeys.value];
    closeKeyDrawer();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    creatingKey.value = false;
  }
}

async function disableKey(key: AdminResource) {
  if (!selectedAccount.value) return;
  openConfirm({
    title: "禁用 API Key",
    message: `禁用 ${key.name || key.id}。`,
    warning: "依赖该 Key 的自动化任务会在下一次调用时认证失败。",
    items: [
      { label: t("name"), value: String(key.name || key.id) },
      { label: t("scopes"), value: listValue(key.scopes) },
      { label: t("status"), value: String(key.status || "active") },
    ],
    action: async () => {
      if (!selectedAccount.value) return;
      const disabled = await consoleClient.disableServiceAccountApiKey(selectedAccount.value.id, key.id);
      apiKeys.value = apiKeys.value.map((item) => (item.id === disabled.id ? disabled : item));
    },
  });
}

function openKeyDrawer() {
  keyForm.name = "";
  keyForm.scopes = selectedAccountPermissions.value.length > 0 ? [...selectedAccountPermissions.value] : ["agent:read"];
  keyForm.expires_at = "";
  keyDrawerOpen.value = true;
}

function openServiceAccountDrawer() {
  serviceAccountDrawerMode.value = "create";
  const scope = readCurrentScope();
  serviceAccountForm.name = "";
  serviceAccountForm.tenant_id = scope.tenant_id;
  serviceAccountForm.project_id = scope.project_id;
  serviceAccountForm.status = "active";
  serviceAccountForm.permissions = ["agent:read"];
  mutationError.value = null;
  serviceAccountDrawerOpen.value = true;
  void loadOptions();
}

function openServiceAccountEditDrawer() {
  if (!selectedAccount.value) return;
  serviceAccountDrawerMode.value = "edit";
  serviceAccountForm.name = String(selectedAccount.value.name || "");
  serviceAccountForm.tenant_id = String(selectedAccount.value.tenant_id || readCurrentScope().tenant_id);
  serviceAccountForm.project_id = String(selectedAccount.value.project_id || readCurrentScope().project_id);
  serviceAccountForm.status = String(selectedAccount.value.status || "active");
  serviceAccountForm.permissions = Array.isArray(selectedAccount.value.permissions) ? selectedAccount.value.permissions.map(String) : [];
  mutationError.value = null;
  serviceAccountDrawerOpen.value = true;
  void loadOptions();
}

function closeServiceAccountDrawer() {
  serviceAccountDrawerOpen.value = false;
  mutationError.value = null;
}

async function deleteServiceAccount() {
  if (!selectedAccount.value) return;
  const account = selectedAccount.value;
  openConfirm({
    title: "删除服务账号",
    message: `删除服务账号 ${account.name || account.id}。`,
    warning: "服务账号会被软删除，关联 API Key 将不可继续用于机器访问。",
    items: [
      { label: t("name"), value: String(account.name || account.id) },
      { label: t("tenant"), value: String(account.tenant_id || "-") },
      { label: t("project"), value: String(account.project_id || "-") },
    ],
    action: async () => {
      const deleted = await consoleClient.deleteServiceAccount(account.id);
      serviceAccounts.value = serviceAccounts.value.filter((item) => item.id !== deleted.id);
      selectedAccount.value = serviceAccounts.value[0] || null;
      apiKeys.value = [];
      if (selectedAccount.value) await loadKeys(selectedAccount.value.id);
    },
  });
}

function closeKeyDrawer() {
  keyDrawerOpen.value = false;
  mutationError.value = null;
}

function openConfirm(payload: Omit<typeof confirmState, "open">) {
  confirmState.title = payload.title;
  confirmState.message = payload.message;
  confirmState.warning = payload.warning;
  confirmState.items = payload.items;
  confirmState.action = payload.action;
  mutationError.value = null;
  confirmState.open = true;
}

function closeConfirm() {
  confirmState.open = false;
  confirmState.action = null;
}

async function runConfirmedAction() {
  if (!confirmState.action) return;
  creatingServiceAccount.value = true;
  mutationError.value = null;
  try {
    await confirmState.action();
    closeConfirm();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    creatingServiceAccount.value = false;
  }
}

async function loadOptions() {
  if (mode === "offline") return;
  const [tenantsPage, permissionsPage] = await Promise.all([
    consoleClient.listAdminCollection("/v1/identity/tenants"),
    consoleClient.listAdminCollection("/v1/identity/permissions"),
  ]);
  tenantOptions.value = tenantsPage.items;
  permissionOptions.value = permissionsPage.items;
  if (!tenantOptions.value.some((tenant) => tenant.id === serviceAccountForm.tenant_id)) {
    serviceAccountForm.tenant_id = tenantOptions.value[0]?.id || "";
  }
  await loadProjects();
}

async function loadProjects() {
  if (!serviceAccountForm.tenant_id) {
    projectOptions.value = [];
    serviceAccountForm.project_id = "";
    return;
  }
  projectOptions.value = (
    await consoleClient.listAdminCollection("/v1/identity/projects", {
      tenant_id: serviceAccountForm.tenant_id,
    })
  ).items;
  if (!projectOptions.value.some((project) => project.id === serviceAccountForm.project_id)) {
    serviceAccountForm.project_id = projectOptions.value[0]?.id || "";
  }
}

async function onTenantChange() {
  await loadProjects();
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value || "-");
}

onMounted(load);
</script>

<style scoped>
.machine-layout {
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  gap: 14px;
}

.account-list,
.account-detail {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.account-list {
  display: grid;
  align-content: start;
  overflow: hidden;
}

.account-row {
  display: grid;
  gap: 4px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  padding: 12px;
  text-align: left;
}

.account-row.active {
  background: var(--color-accent-soft);
}

.account-row small,
.detail-header p {
  color: var(--color-text-muted);
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.detail-header h2 {
  margin: 0;
}

.embedded {
  border: 0;
  border-radius: 0;
}

.secret-once {
  display: grid;
  gap: 8px;
  margin: 14px;
  border: 1px solid color-mix(in srgb, var(--color-warning) 45%, var(--color-border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-warning) 11%, var(--color-surface));
  padding: 12px;
}

.secret-once code {
  overflow-wrap: anywhere;
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
  width: min(460px, 100%);
  grid-template-rows: auto 1fr;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.drawer-header,
.drawer-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 18px;
}

.drawer-actions {
  justify-content: flex-end;
  border-top: 1px solid var(--color-border);
  border-bottom: 0;
  margin: 8px -18px -18px;
  padding: 14px 18px;
}

.drawer-form {
  display: grid;
  align-content: start;
  gap: 14px;
  overflow: auto;
  padding: 18px;
}

.permission-fieldset {
  display: grid;
  max-height: 280px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 8px 0 0;
}

.permission-fieldset legend {
  padding: 0 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.permission-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
}

.permission-row.compact {
  border-bottom: 1px solid var(--color-border);
}

.permission-row small {
  display: block;
  color: var(--color-text-muted);
  font-size: 12px;
}

@media (max-width: 900px) {
  .machine-layout {
    grid-template-columns: 1fr;
  }
}
</style>
