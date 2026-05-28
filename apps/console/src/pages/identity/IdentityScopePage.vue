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
            <th v-if="activeTab !== 'tenants'">{{ t("tenant") }}</th>
            <th v-if="activeTab === 'environments'">{{ t("project") }}</th>
            <th v-if="activeTab === 'environments'">{{ t("environment") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("updatedAt") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td><strong>{{ item.name || item.slug || item.environment }}</strong></td>
            <td class="mono">{{ item.id }}</td>
            <td v-if="activeTab !== 'tenants'" class="mono muted">{{ item.tenant_id || "-" }}</td>
            <td v-if="activeTab === 'environments'" class="mono muted">{{ item.project_id || "-" }}</td>
            <td v-if="activeTab === 'environments'" class="mono muted">{{ item.environment || "-" }}</td>
            <td><StatusBadge :status="String(item.status || 'active')" :label="String(item.status || 'active')" /></td>
            <td>{{ item.updated_at || "-" }}</td>
            <td>
              <div class="row-actions">
                <button class="button" type="button" :disabled="!canWrite" @click="openEditDrawer(item)">编辑</button>
                <button class="button danger" type="button" :disabled="!canWrite" @click="deleteItem(item)">{{ t("delete") }}</button>
              </div>
            </td>
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
              <h2>{{ drawerMode === "create" ? t("create") : "编辑" }} {{ activeLabel }}</h2>
            </div>
            <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="saveItem">
            <label class="field">
              {{ t("name") }}
              <input v-model="form.name" class="input" required />
            </label>
            <label v-if="activeTab !== 'tenants'" class="field">
              {{ t("tenant") }}
              <select v-model="form.tenant_id" class="select" required :disabled="loadingParents || tenantOptions.length === 0" @change="onTenantChange">
                <option v-if="tenantOptions.length === 0" value="">{{ loadingParents ? t("loading") : "-" }}</option>
                <option v-for="tenant in tenantOptions" :key="tenant.id" :value="tenant.id">
                  {{ optionLabel(tenant) }}
                </option>
              </select>
            </label>
            <label v-if="activeTab === 'environments'" class="field">
              {{ t("project") }}
              <select v-model="form.project_id" class="select" required :disabled="loadingParents || projectOptions.length === 0">
                <option v-if="projectOptions.length === 0" value="">{{ loadingParents ? t("loading") : "-" }}</option>
                <option v-for="project in projectOptions" :key="project.id" :value="project.id">
                  {{ optionLabel(project) }}
                </option>
              </select>
            </label>
            <label v-if="activeTab !== 'tenants'" class="field">
              {{ t("environment") }}
              <input v-if="activeTab === 'environments'" v-model="form.environment" class="input" required placeholder="prod" />
              <input v-else class="input" disabled value="-" />
            </label>
            <InlineApiError :error="mutationError" />
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creating || loadingParents || !canSubmit">
                {{ creating ? t("creating") : t("save") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <DangerConfirmDialog
      :open="confirmState.open"
      title="删除组织范围"
      :message="confirmState.message"
      :items="confirmState.items"
      :error="mutationError"
      warning="删除后会影响依赖该租户、项目或环境的权限范围与业务配置。"
      :busy="creating"
      confirm-label="确认删除"
      @cancel="closeConfirm"
      @confirm="runConfirmedDelete"
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

type ScopeTab = "tenants" | "projects" | "environments";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const activeTab = ref<ScopeTab>("tenants");
const items = ref<AdminResource[]>([]);
const tenantOptions = ref<AdminResource[]>([]);
const projectOptions = ref<AdminResource[]>([]);
const loading = ref(false);
const loadingParents = ref(false);
const creating = ref(false);
const drawerOpen = ref(false);
const drawerMode = ref<"create" | "edit">("create");
const editingItem = ref<AdminResource | null>(null);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const form = reactive({ name: "", tenant_id: "", project_id: "", environment: "" });
const confirmState = reactive({
  open: false,
  item: null as AdminResource | null,
  message: "",
  items: [] as Array<{ label: string; value: string }>,
});
const tabs = computed(() => [
  { key: "tenants" as const, label: t("tenants") },
  { key: "projects" as const, label: t("projects") },
  { key: "environments" as const, label: t("environments") },
]);
const activeLabel = computed(() => tabs.value.find((tab) => tab.key === activeTab.value)?.label || "");
const canWrite = computed(() => auth.can("identity:scope:write"));
const canSubmit = computed(() => {
  if (!form.name.trim()) return false;
  if (activeTab.value === "projects") return Boolean(form.tenant_id);
  if (activeTab.value === "environments") return Boolean(form.tenant_id && form.project_id && form.environment.trim());
  return true;
});

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

async function saveItem() {
  if (!canWrite.value) return;
  creating.value = true;
  mutationError.value = null;
  try {
    const scope = readCurrentScope();
    const payload: Record<string, unknown> = { name: form.name };
    const slug = slugify(form.name);
    if (activeTab.value !== "environments" && slug) payload.slug = slug;
    if (activeTab.value === "projects") payload.tenant_id = form.tenant_id || scope.tenant_id;
    if (activeTab.value === "environments") {
      payload.tenant_id = form.tenant_id || scope.tenant_id;
      payload.project_id = form.project_id || scope.project_id;
      payload.environment = form.environment || form.name;
    }
    const item =
      drawerMode.value === "create"
        ? await consoleClient.createAdminItem(`/v1/identity/${activeTab.value}`, payload)
        : editingItem.value
          ? await consoleClient.updateAdminItem(`/v1/identity/${activeTab.value}`, editingItem.value.id, payload)
          : null;
    if (!item) return;
    items.value =
      drawerMode.value === "create"
        ? [item, ...items.value]
        : items.value.map((current) => (current.id === item.id ? item : current));
    closeDrawer();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function setTab(tab: ScopeTab) {
  activeTab.value = tab;
  loadItems();
}

function openDrawer() {
  drawerMode.value = "create";
  editingItem.value = null;
  const scope = readCurrentScope();
  form.name = "";
  form.tenant_id = scope.tenant_id;
  form.project_id = scope.project_id;
  form.environment = scope.environment;
  drawerOpen.value = true;
  mutationError.value = null;
  void loadParentOptions();
}

function openEditDrawer(item: AdminResource) {
  drawerMode.value = "edit";
  editingItem.value = item;
  form.name = String(item.name || "");
  form.tenant_id = String(item.tenant_id || readCurrentScope().tenant_id);
  form.project_id = String(item.project_id || readCurrentScope().project_id);
  form.environment = String(item.environment || "");
  drawerOpen.value = true;
  mutationError.value = null;
  void loadParentOptions();
}

function closeDrawer() {
  drawerOpen.value = false;
  editingItem.value = null;
  mutationError.value = null;
}

async function deleteItem(item: AdminResource) {
  confirmState.item = item;
  confirmState.message = `删除 ${optionLabel(item)}。`;
  confirmState.items = [
    { label: t("name"), value: optionLabel(item) },
    { label: t("id"), value: item.id },
    { label: t("status"), value: String(item.status || "active") },
  ];
  mutationError.value = null;
  confirmState.open = true;
}

function closeConfirm() {
  confirmState.open = false;
  confirmState.item = null;
}

async function runConfirmedDelete() {
  if (!confirmState.item) return;
  creating.value = true;
  mutationError.value = null;
  try {
    const deleted = await consoleClient.deleteAdminItem(`/v1/identity/${activeTab.value}`, confirmState.item.id);
    items.value = items.value.filter((current) => current.id !== deleted.id);
    closeConfirm();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

async function loadParentOptions() {
  tenantOptions.value = [];
  projectOptions.value = [];
  if (mode === "offline" || activeTab.value === "tenants") return;
  loadingParents.value = true;
  error.value = null;
  try {
    tenantOptions.value = (await consoleClient.listAdminCollection("/v1/identity/tenants")).items;
    if (!tenantOptions.value.some((tenant) => tenant.id === form.tenant_id)) {
      form.tenant_id = tenantOptions.value[0]?.id || "";
    }
    if (activeTab.value === "environments") await loadProjectOptions();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loadingParents.value = false;
  }
}

async function loadProjectOptions() {
  projectOptions.value = [];
  if (!form.tenant_id) {
    form.project_id = "";
    return;
  }
  const projects = (await consoleClient.listAdminCollection("/v1/identity/projects", { tenant_id: form.tenant_id })).items;
  projectOptions.value = projects;
  if (!projectOptions.value.some((project) => project.id === form.project_id)) {
    form.project_id = projectOptions.value[0]?.id || "";
  }
}

async function onTenantChange() {
  if (activeTab.value !== "environments") return;
  loadingParents.value = true;
  error.value = null;
  try {
    await loadProjectOptions();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loadingParents.value = false;
  }
}

function optionLabel(item: AdminResource): string {
  return String(item.name || item.slug || item.environment || item.id);
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

.row-actions {
  display: flex;
  gap: 6px;
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
