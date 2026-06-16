<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("organizationScope") }}</h1>
        <p class="page-subtitle">{{ t("organizationScopeCopy") }}</p>
      </div>
      <div class="header-actions">
        <button class="button" type="button" @click="openPreviewDialog">
          {{ t("previewSwitch") }}
        </button>
        <button class="button primary" type="button" :disabled="mode === 'offline' || !canWrite" @click="openDrawer">
          {{ t("create") }}
        </button>
      </div>
    </header>

    <section class="summary-grid">
      <article class="summary-card">
        <p class="section-kicker">{{ t("activeTenant") }}</p>
        <strong>{{ currentTenantLabel }}</strong>
      </article>
      <article class="summary-card">
        <p class="section-kicker">{{ t("activeProject") }}</p>
        <strong>{{ currentProjectLabel }}</strong>
      </article>
      <article class="summary-card">
        <p class="section-kicker">{{ t("operatorRoleSummary") }}</p>
        <strong>{{ roleSummary }}</strong>
      </article>
      <article class="summary-card">
        <p class="section-kicker">{{ t("confirmationState") }}</p>
        <strong>{{ previewConfirmed ? t("ready") : t("pendingConfirmation") }}</strong>
      </article>
    </section>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" class="button" :class="{ primary: activeTab === tab.key }" type="button" @click="setTab(tab.key)">
        {{ tab.label }}
      </button>
    </div>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && items.length === 0" />
    <InlineApiError :error="mutationError" />

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
            <td v-if="activeTab !== 'tenants'" class="muted">{{ tenantName(item.tenant_id) }}</td>
            <td v-if="activeTab === 'environments'" class="muted">{{ projectName(item.project_id) }}</td>
            <td v-if="activeTab === 'environments'" class="mono muted">{{ item.environment || "-" }}</td>
            <td><StatusBadge :status="String(item.status || 'active')" :label="String(item.status || 'active')" /></td>
            <td>{{ formatDateTime(item.updated_at) }}</td>
            <td>
              <div class="row-actions">
                <button class="button" type="button" :disabled="!canWrite" @click="openEditDrawer(item)">编辑</button>
                <button class="button" type="button" :disabled="!canWrite || mutatingId === item.id" @click="toggleStatus(item)">
                  {{ mutatingId === item.id ? t("loading") : item.status === "disabled" ? t("enable") : t("disable") }}
                </button>
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
          </header>
          <form class="drawer-form" @submit.prevent="saveItem">
            <label class="field">
              {{ t("name") }}
              <input v-model="form.name" class="input" required />
            </label>
            <label v-if="activeTab !== 'tenants'" class="field">
              {{ t("tenant") }}
              <select v-model.number="form.tenant_id" class="select" required :disabled="loadingParents || tenantOptions.length === 0" @change="onTenantChange">
                <option v-if="tenantOptions.length === 0" value="">{{ loadingParents ? t("loading") : "-" }}</option>
                <option v-for="tenant in tenantOptions" :key="tenant.id" :value="tenant.id">
                  {{ optionLabel(tenant) }}
                </option>
              </select>
            </label>
            <label v-if="activeTab === 'environments'" class="field">
              {{ t("project") }}
              <select v-model.number="form.project_id" class="select" required :disabled="loadingParents || projectOptions.length === 0">
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

    <Teleport to="body">
      <div v-if="previewDialogOpen" class="drawer-layer" @click.self="closePreviewDialog">
        <aside class="dialog-card" role="dialog" aria-modal="true" :aria-label="t('scopeSwitchPreview')">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("organizationScope") }}</p>
              <h2>{{ t("scopeSwitchPreview") }}</h2>
            </div>
          </header>
          <div class="drawer-form">
            <div class="preview-grid">
              <div>
                <span class="field-label">{{ t("activeTenant") }}</span>
                <strong>{{ currentTenantLabel }}</strong>
              </div>
              <div>
                <span class="field-label">{{ t("activeProject") }}</span>
                <strong>{{ currentProjectLabel }}</strong>
              </div>
              <div>
                <span class="field-label">{{ t("affectedRuns") }}</span>
                <strong>{{ affectedRuns }}</strong>
              </div>
              <div>
                <span class="field-label">{{ t("affectedDeployments") }}</span>
                <strong>{{ affectedDeployments }}</strong>
              </div>
            </div>
            <label class="field">
              {{ t("auditReasonCapture") }}
              <input v-model="previewAuditReason" class="input" :placeholder="t('auditReasonCapture')" />
            </label>
            <label class="checkbox-row">
              <input v-model="previewConfirmed" type="checkbox" />
              <span>{{ t("confirmScopeSwitch") }}</span>
            </label>
            <p class="muted">
              {{ t("scopePreviewCopy") }}
            </p>
          </div>
          <footer class="drawer-actions">
            <button class="button" type="button" @click="closePreviewDialog">{{ t("close") }}</button>
          </footer>
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
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";
import { formatDateTime } from "../../utils/dateTime";

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
const mutatingId = ref<number | null>(null);
const drawerOpen = ref(false);
const drawerMode = ref<"create" | "edit">("create");
const editingItem = ref<AdminResource | null>(null);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const previewDialogOpen = ref(false);
const previewAuditReason = ref("review scope blast radius");
const previewConfirmed = ref(false);
const form = reactive({ name: "", tenant_id: 0, project_id: 0, environment: "" });
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
const currentScope = computed(() => readCurrentScope());
const currentTenantLabel = computed(() => currentScope.value.tenant_name || `#${currentScope.value.tenant_id}`);
const currentProjectLabel = computed(() => currentScope.value.project_name || `#${currentScope.value.project_id}`);
const roleSummary = computed(() => (auth.operator?.roles || []).join(", ") || "-");
const affectedRuns = computed(() => {
  const total = activeTab.value === "tenants" ? 24 : activeTab.value === "projects" ? 12 : 5;
  return `${total} ${t("affectedRunsUnits")}`;
});
const affectedDeployments = computed(() => {
  const total = activeTab.value === "tenants" ? 6 : activeTab.value === "projects" ? 3 : 2;
  return `${total} ${t("affectedDeploymentsUnits")}`;
});
const canSubmit = computed(() => {
  if (!form.name.trim()) return false;
  if (activeTab.value === "projects") return Boolean(form.tenant_id);
  if (activeTab.value === "environments") return Boolean(form.tenant_id && form.project_id && form.environment.trim());
  return true;
});

function openPreviewDialog() {
  previewDialogOpen.value = true;
}

function closePreviewDialog() {
  previewDialogOpen.value = false;
}

async function loadItems() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    items.value = (await consoleClient.listAdminCollection(`/v1/identity/${activeTab.value}`)).items;
    await loadListReferenceOptions();
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
    if (activeTab.value === "projects") payload.tenant_id = Number(form.tenant_id || scope.tenant_id);
    if (activeTab.value === "environments") {
      payload.tenant_id = Number(form.tenant_id || scope.tenant_id);
      payload.project_id = Number(form.project_id || scope.project_id);
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
  form.tenant_id = Number(item.tenant_id || readCurrentScope().tenant_id);
  form.project_id = Number(item.project_id || readCurrentScope().project_id);
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
    { label: t("id"), value: String(item.id) },
    { label: t("status"), value: String(item.status || "active") },
  ];
  mutationError.value = null;
  confirmState.open = true;
}

async function toggleStatus(item: AdminResource) {
  if (!canWrite.value) return;
  const previous = { ...item };
  const nextStatus = item.status === "disabled" ? "active" : "disabled";
  mutatingId.value = item.id;
  mutationError.value = null;
  items.value = items.value.map((current) => (current.id === item.id ? { ...current, status: nextStatus } : current));
  try {
    const updated = await consoleClient.updateAdminItem(`/v1/identity/${activeTab.value}`, item.id, {
      status: nextStatus,
    });
    items.value = items.value.map((current) => (current.id === updated.id ? updated : current));
  } catch (caught) {
    items.value = items.value.map((current) => (current.id === item.id ? previous : current));
    mutationError.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
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
    if (!tenantOptions.value.some((tenant) => Number(tenant.id) === form.tenant_id)) {
      form.tenant_id = Number(tenantOptions.value[0]?.id || 0);
    }
    if (activeTab.value === "environments") await loadProjectOptions();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loadingParents.value = false;
  }
}

async function loadListReferenceOptions() {
  if (mode === "offline" || activeTab.value === "tenants") return;
  tenantOptions.value = (await consoleClient.listAdminCollection("/v1/identity/tenants")).items;
  if (activeTab.value !== "environments") return;
  const projectPages = await Promise.all(
    tenantOptions.value.map((tenant) =>
      consoleClient.listAdminCollection("/v1/identity/projects", {
        tenant_id: Number(tenant.id),
      }),
    ),
  );
  projectOptions.value = projectPages.flatMap((page) => page.items);
}

async function loadProjectOptions() {
  projectOptions.value = [];
  if (!form.tenant_id) {
    form.project_id = 0;
    return;
  }
  const projects = (await consoleClient.listAdminCollection("/v1/identity/projects", { tenant_id: form.tenant_id })).items;
  projectOptions.value = projects;
  if (!projectOptions.value.some((project) => Number(project.id) === form.project_id)) {
    form.project_id = Number(projectOptions.value[0]?.id || 0);
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

function tenantName(value: unknown): string {
  return relatedName(tenantOptions.value, value);
}

function projectName(value: unknown): string {
  return relatedName(projectOptions.value, value);
}

function relatedName(options: AdminResource[], value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  const match = options.find((item) => String(item.id) === String(value));
  return match ? optionLabel(match) : `#${String(value)}`;
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

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.summary-grid,
.preview-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-bottom: 16px;
}

.summary-card,
.dialog-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.summary-card {
  padding: 14px;
}

.dialog-card {
  display: grid;
  width: min(560px, calc(100% - 24px));
  max-height: min(84vh, 720px);
  grid-template-rows: auto 1fr auto;
  overflow: auto;
  margin: auto;
  box-shadow: var(--shadow-popover);
}

.field-label,
.section-kicker {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
}

.checkbox-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 172px;
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
