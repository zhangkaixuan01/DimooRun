<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("organizationScope") }}</h1>
        <p class="page-subtitle">{{ t("organizationScopeCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canWrite" @click="openDrawer">
        {{ t("create") }}
      </button>
    </header>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" class="button" :class="{ primary: activeTab === tab.key }" type="button" @click="setTab(tab.key)">
        {{ tab.label }}
      </button>
    </div>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && items.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && items.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("name") }}</th>
            <th>{{ t("id") }}</th>
            <th>{{ t("tenant") }}</th>
            <th>{{ t("project") }}</th>
            <th>{{ t("environment") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("updatedAt") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td><strong>{{ item.name || item.slug || item.environment }}</strong></td>
            <td class="mono">{{ item.id }}</td>
            <td class="mono muted">{{ item.tenant_id || "-" }}</td>
            <td class="mono muted">{{ item.project_id || "-" }}</td>
            <td class="mono muted">{{ item.environment || "-" }}</td>
            <td><StatusBadge :status="String(item.status || 'active')" :label="String(item.status || 'active')" /></td>
            <td>{{ item.updated_at || "-" }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="drawerOpen" class="drawer-layer" @click.self="closeDrawer">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("organizationScope") }}</p>
              <h2>{{ t("create") }} {{ activeLabel }}</h2>
            </div>
            <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="createItem">
            <label class="field">
              {{ t("name") }}
              <input v-model="form.name" class="input" required />
            </label>
            <label v-if="activeTab !== 'tenants'" class="field">
              {{ t("tenant") }}
              <input v-model="form.tenant_id" class="input" required />
            </label>
            <label v-if="activeTab === 'environments'" class="field">
              {{ t("project") }}
              <input v-model="form.project_id" class="input" required />
            </label>
            <label v-if="activeTab !== 'tenants'" class="field">
              {{ t("environment") }}
              <input v-if="activeTab === 'environments'" v-model="form.environment" class="input" required placeholder="prod" />
              <input v-else class="input" disabled value="-" />
            </label>
            <label class="field">
              {{ t("slug") }}
              <input v-model="form.slug" class="input" />
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creating">{{ creating ? t("creating") : t("save") }}</button>
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

type ScopeTab = "tenants" | "projects" | "environments";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const activeTab = ref<ScopeTab>("tenants");
const items = ref<AdminResource[]>([]);
const loading = ref(false);
const creating = ref(false);
const drawerOpen = ref(false);
const error = ref<ConsoleApiError | null>(null);
const form = reactive({ name: "", slug: "", tenant_id: "", project_id: "", environment: "" });
const tabs = computed(() => [
  { key: "tenants" as const, label: t("tenants") },
  { key: "projects" as const, label: t("projects") },
  { key: "environments" as const, label: t("environments") },
]);
const activeLabel = computed(() => tabs.value.find((tab) => tab.key === activeTab.value)?.label || "");
const canWrite = computed(() => auth.can("identity:scope:write"));

async function loadItems() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    items.value = (await consoleClient.listAdminCollection(`/v1/identity/${activeTab.value}`)).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createItem() {
  if (!canWrite.value) return;
  creating.value = true;
  error.value = null;
  try {
    const scope = readCurrentScope();
    const payload: Record<string, unknown> = { name: form.name, slug: form.slug || form.name };
    if (activeTab.value === "projects") payload.tenant_id = form.tenant_id || scope.tenant_id;
    if (activeTab.value === "environments") {
      payload.tenant_id = form.tenant_id || scope.tenant_id;
      payload.project_id = form.project_id || scope.project_id;
      payload.environment = form.environment || form.name;
    }
    const item = await consoleClient.createAdminItem(`/v1/identity/${activeTab.value}`, payload);
    items.value = [item, ...items.value];
    closeDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function setTab(tab: ScopeTab) {
  activeTab.value = tab;
  loadItems();
}

function openDrawer() {
  const scope = readCurrentScope();
  form.name = "";
  form.slug = "";
  form.tenant_id = scope.tenant_id;
  form.project_id = scope.project_id;
  form.environment = scope.environment;
  drawerOpen.value = true;
}

function closeDrawer() {
  drawerOpen.value = false;
}

onMounted(loadItems);
</script>

<style scoped>
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
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
</style>
