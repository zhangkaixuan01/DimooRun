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
          <button class="button primary" type="button" :disabled="!selectedAccount || !canWriteApiKey" @click="openKeyDrawer">
            {{ t("createApiKey") }}
          </button>
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
              <h2>{{ t("create") }} {{ t("serviceAccounts") }}</h2>
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
              <input v-model="serviceAccountForm.tenant_id" class="input" required />
            </label>
            <label class="field">
              {{ t("project") }}
              <input v-model="serviceAccountForm.project_id" class="input" />
            </label>
            <label class="field">
              {{ t("permissions") }}
              <input v-model="serviceAccountForm.permissions" class="input" required placeholder="agent:read, run:create" />
            </label>
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
              <input v-model="keyForm.scopes" class="input" required placeholder="agent:read, agent:deploy" />
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeKeyDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingKey">{{ creatingKey ? t("creating") : t("save") }}</button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const serviceAccounts = ref<AdminResource[]>([]);
const selectedAccount = ref<AdminResource | null>(null);
const apiKeys = ref<AdminResource[]>([]);
const loading = ref(false);
const creatingServiceAccount = ref(false);
const creatingKey = ref(false);
const serviceAccountDrawerOpen = ref(false);
const keyDrawerOpen = ref(false);
const oneTimeKey = ref("");
const error = ref<ConsoleApiError | null>(null);
const serviceAccountForm = reactive({ name: "", tenant_id: "", project_id: "", permissions: "agent:read" });
const keyForm = reactive({ name: "", scopes: "agent:read" });
const canWriteServiceAccount = computed(() => auth.can("service_account:write") || auth.can("admin:write"));
const canWriteApiKey = computed(() => auth.can("api_key:write") || auth.can("admin:write"));

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    serviceAccounts.value = (await consoleClient.listServiceAccounts()).items;
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
  error.value = null;
  try {
    const account = await consoleClient.createServiceAccount({
      name: serviceAccountForm.name,
      tenant_id: serviceAccountForm.tenant_id,
      project_id: serviceAccountForm.project_id || null,
      permissions: csv(serviceAccountForm.permissions),
    });
    serviceAccounts.value = [account, ...serviceAccounts.value];
    closeServiceAccountDrawer();
    await selectAccount(account);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
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
  error.value = null;
  try {
    const response = await consoleClient.createServiceAccountApiKey(selectedAccount.value.id, {
      name: keyForm.name,
      scopes: csv(keyForm.scopes),
    });
    oneTimeKey.value = response.plain_key;
    apiKeys.value = [response.item, ...apiKeys.value];
    closeKeyDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingKey.value = false;
  }
}

async function disableKey(key: AdminResource) {
  if (!selectedAccount.value) return;
  const disabled = await consoleClient.disableServiceAccountApiKey(selectedAccount.value.id, key.id);
  apiKeys.value = apiKeys.value.map((item) => (item.id === disabled.id ? disabled : item));
}

function openKeyDrawer() {
  keyForm.name = "";
  keyForm.scopes = Array.isArray(selectedAccount.value?.permissions)
    ? selectedAccount.value.permissions.map(String).join(", ")
    : "agent:read";
  keyDrawerOpen.value = true;
}

function openServiceAccountDrawer() {
  const scope = readCurrentScope();
  serviceAccountForm.name = "";
  serviceAccountForm.tenant_id = scope.tenant_id;
  serviceAccountForm.project_id = scope.project_id;
  serviceAccountForm.permissions = "agent:read";
  serviceAccountDrawerOpen.value = true;
}

function closeServiceAccountDrawer() {
  serviceAccountDrawerOpen.value = false;
}

function closeKeyDrawer() {
  keyDrawerOpen.value = false;
}

function csv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
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

@media (max-width: 900px) {
  .machine-layout {
    grid-template-columns: 1fr;
  }
}
</style>
