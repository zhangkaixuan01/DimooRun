<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("operators") }}</h1>
        <p class="page-subtitle">{{ t("operatorsCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canManageOperators" @click="openCreateDrawer">
        {{ t("create") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && operators.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && operators.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("name") }}</th>
            <th>{{ t("email") }}</th>
            <th>{{ t("roles") }}</th>
            <th>{{ t("permissions") }}</th>
            <th>{{ t("allowedScopes") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("lastUsed") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="operator in operators" :key="operator.id">
            <td><strong>{{ operator.name }}</strong><br /><span class="mono muted">{{ operator.id }}</span></td>
            <td>{{ operator.email }}</td>
            <td>{{ listValue(operator.roles) }}</td>
            <td>{{ listValue(operator.permissions) }}</td>
            <td class="mono muted">{{ scopeValue(operator.allowed_scopes) }}</td>
            <td><StatusBadge :status="String(operator.status || 'active')" :label="String(operator.status || 'active')" /></td>
            <td>{{ operator.last_login_at || "-" }}</td>
            <td>
              <div class="row-actions">
                <button class="button" type="button" :disabled="!canManageOperators" @click="openEditDrawer(operator)">编辑</button>
                <button class="button" type="button" :disabled="!canManageOperators" @click="openPasswordDrawer(operator)">重置密码</button>
                <button class="button" type="button" :disabled="!canManageOperators" @click="revokeSessions(operator)">撤销会话</button>
                <button class="button danger" type="button" :disabled="!canManageOperators" @click="deleteOperator(operator)">{{ t("delete") }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="drawerOpen" class="drawer-layer" @click.self="closeDrawer">
        <aside class="drawer" :aria-label="drawerMode === 'create' ? t('create') : '编辑'" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("identity") }}</p>
              <h2>{{ drawerMode === "create" ? t("create") : "编辑" }} {{ t("operators") }}</h2>
            </div>
            <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="saveOperator">
            <label class="field">
              {{ t("name") }}
              <input v-model.trim="form.name" class="input" required placeholder="Ops Operator" />
            </label>
            <label class="field">
              {{ t("email") }}
              <input v-model.trim="form.email" class="input" autocomplete="username" :disabled="drawerMode === 'edit'" required type="email" />
            </label>
            <label v-if="drawerMode === 'create'" class="field">
              {{ t("initialPassword") }}
              <input v-model="form.password" class="input" autocomplete="new-password" required type="password" />
            </label>
            <label class="field">
              {{ t("status") }}
              <select v-model="form.status" class="select">
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </select>
            </label>
            <label class="field">
              {{ t("roles") }}
              <select v-model="form.roles" class="select" multiple required>
                <option v-for="role in roleOptions" :key="role.id" :value="String(role.name || role.id)">
                  {{ role.name || role.id }}
                </option>
              </select>
            </label>
            <fieldset class="permission-fieldset">
              <legend>{{ t("permissions") }}</legend>
              <label v-for="permission in permissionOptions" :key="permission.id" class="permission-row compact">
                <input v-model="form.permissions" type="checkbox" :value="String(permission.code || permission.name)" />
                <span>
                  <strong class="mono">{{ permission.code || permission.name }}</strong>
                  <small>{{ permission.resource || "-" }} / {{ permission.action || "-" }}</small>
                </span>
              </label>
            </fieldset>

            <section class="scope-editor">
              <div class="scope-editor-header">
                <strong>{{ t("allowedScopes") }}</strong>
                <button class="button" type="button" @click="addScope">新增范围</button>
              </div>
              <div v-for="(scope, index) in form.allowed_scopes" :key="index" class="scope-grid">
                <label class="field">
                  {{ t("tenant") }}
                  <select v-model="scope.tenant_id" class="select" required @change="onScopeTenantChange(scope)">
                    <option v-for="tenant in tenantOptions" :key="tenant.id" :value="tenant.id">{{ tenant.name || tenant.id }}</option>
                  </select>
                </label>
                <label class="field">
                  {{ t("project") }}
                  <select v-model="scope.project_id" class="select" required @focus="loadScopeProjects(scope)">
                    <option v-for="project in projectOptionsFor(scope.tenant_id)" :key="project.id" :value="project.id">{{ project.name || project.id }}</option>
                  </select>
                </label>
                <label class="field">
                  {{ t("environment") }}
                  <select v-model="scope.environment" class="select" required @focus="loadScopeEnvironments(scope)">
                    <option v-for="environment in environmentOptionsFor(scope.tenant_id, scope.project_id)" :key="environment.id" :value="String(environment.environment || environment.id)">
                      {{ environment.name || environment.environment || environment.id }}
                    </option>
                  </select>
                </label>
                <button class="button danger" type="button" :disabled="form.allowed_scopes.length === 1" @click="removeScope(index)">{{ t("delete") }}</button>
              </div>
            </section>

            <section v-if="drawerMode === 'edit'" class="session-panel">
              <div class="scope-editor-header">
                <strong>会话</strong>
                <button class="button" type="button" :disabled="sessionLoading || !editingOperator" @click="reloadEditingSessions">
                  {{ sessionLoading ? t("loading") : "刷新" }}
                </button>
              </div>
              <div v-if="sessions.length === 0" class="muted">暂无会话</div>
              <div v-else class="session-list">
                <article v-for="session in sessions" :key="session.id" class="session-row">
                  <div>
                    <strong class="mono">{{ session.id }}</strong>
                    <small>{{ session.ip_address || "-" }} · {{ session.user_agent || "-" }}</small>
                  </div>
                  <StatusBadge :status="session.status" :label="session.status" />
                  <small>last={{ session.last_used_at || "-" }}</small>
                  <small>expires={{ session.expires_at || "-" }}</small>
                </article>
              </div>
            </section>

            <InlineApiError :error="mutationError" />

            <div class="drawer-actions">
              <button class="button" type="button" @click="closeDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="saving || !canSubmit">
                {{ saving ? t("loading") : t("save") }}
              </button>
            </div>
          </form>
        </aside>
      </div>

      <div v-if="passwordDrawerOpen" class="drawer-layer" @click.self="closePasswordDrawer">
        <aside class="drawer narrow" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("operators") }}</p>
              <h2>重置密码</h2>
            </div>
            <button class="button" type="button" @click="closePasswordDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="resetPassword">
            <label class="field">
              {{ t("initialPassword") }}
              <input v-model="passwordForm.new_password" class="input" autocomplete="new-password" required type="password" />
            </label>
            <InlineApiError :error="mutationError" />
            <div class="drawer-actions">
              <button class="button" type="button" @click="closePasswordDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="saving || passwordForm.new_password.length < 8">{{ t("save") }}</button>
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
      :busy="saving"
      confirm-label="确认执行"
      @cancel="closeConfirm"
      @confirm="runConfirmedAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError, type ConsoleOperator, type ConsoleOperatorSession } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

type ScopeForm = { tenant_id: string; project_id: string; environment: string };

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const canManageOperators = computed(() => auth.can("identity:operator:write"));
const loading = ref(false);
const saving = ref(false);
const drawerOpen = ref(false);
const passwordDrawerOpen = ref(false);
const drawerMode = ref<"create" | "edit">("create");
const editingOperator = ref<ConsoleOperator | null>(null);
const passwordOperator = ref<ConsoleOperator | null>(null);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const operators = ref<ConsoleOperator[]>([]);
const sessions = ref<ConsoleOperatorSession[]>([]);
const sessionLoading = ref(false);
const roleOptions = ref<AdminResource[]>([]);
const permissionOptions = ref<AdminResource[]>([]);
const tenantOptions = ref<AdminResource[]>([]);
const projectOptionsByTenant = ref<Record<string, AdminResource[]>>({});
const environmentOptionsByScope = ref<Record<string, AdminResource[]>>({});
const form = reactive({
  name: "",
  email: "",
  password: "",
  status: "active",
  roles: ["runtime_operator"] as string[],
  permissions: ["agent:read", "run:read"] as string[],
  allowed_scopes: [] as ScopeForm[],
});
const passwordForm = reactive({ new_password: "" });
const confirmState = reactive({
  open: false,
  title: "",
  message: "",
  warning: "",
  items: [] as Array<{ label: string; value: string }>,
  action: null as null | (() => Promise<void>),
});
const canSubmit = computed(() => {
  return Boolean(form.name.trim() && form.email.trim() && (drawerMode.value === "edit" || form.password.length >= 8) && form.allowed_scopes.length > 0);
});

async function loadOperators() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const page = (await consoleClient.listAdminCollection("/v1/identity/operators")) as unknown as { items: ConsoleOperator[] };
    operators.value = page.items;
    await loadOptions();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function saveOperator() {
  if (!canManageOperators.value || !canSubmit.value) return;
  saving.value = true;
  mutationError.value = null;
  try {
    if (drawerMode.value === "create") {
      const operator = (await consoleClient.createAdminItem("/v1/identity/operators", operatorPayload(true))) as ConsoleOperator;
      operators.value = [operator, ...operators.value];
    } else if (editingOperator.value) {
      const operator = (await consoleClient.updateAdminItem("/v1/identity/operators", editingOperator.value.id, operatorPayload(false))) as ConsoleOperator;
      operators.value = operators.value.map((item) => (item.id === operator.id ? operator : item));
    }
    closeDrawer();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

function operatorPayload(includePassword: boolean): Record<string, unknown> {
  return {
    email: form.email.trim(),
    name: form.name.trim(),
    ...(includePassword ? { password: form.password } : {}),
    status: form.status,
    roles: form.roles,
    permissions: form.permissions,
    allowed_scopes: form.allowed_scopes.map((scope) => ({ ...scope })),
  };
}

function openCreateDrawer() {
  if (!canManageOperators.value) return;
  drawerMode.value = "create";
  editingOperator.value = null;
  resetForm();
  drawerOpen.value = true;
  void loadOptions();
}

function openEditDrawer(operator: ConsoleOperator) {
  if (!canManageOperators.value) return;
  drawerMode.value = "edit";
  editingOperator.value = operator;
  mutationError.value = null;
  form.name = operator.name;
  form.email = operator.email;
  form.password = "";
  form.status = String(operator.status || "active");
  form.roles = Array.isArray(operator.roles) ? operator.roles.map(String) : [];
  form.permissions = Array.isArray(operator.permissions) ? operator.permissions.map(String) : [];
  form.allowed_scopes = Array.isArray(operator.allowed_scopes) && operator.allowed_scopes.length > 0
    ? operator.allowed_scopes.map((scope) => ({
        tenant_id: String(scope.tenant_id || ""),
        project_id: String(scope.project_id || ""),
        environment: String(scope.environment || ""),
      }))
    : [defaultScope()];
  drawerOpen.value = true;
  void loadOptions();
  void reloadEditingSessions();
}

function closeDrawer() {
  drawerOpen.value = false;
  editingOperator.value = null;
  mutationError.value = null;
  sessions.value = [];
}

function resetForm() {
  const scope = defaultScope();
  form.name = "";
  form.email = "";
  form.password = "";
  form.status = "active";
  form.roles = ["runtime_operator"];
  form.permissions = ["agent:read", "run:read"];
  form.allowed_scopes = [scope];
}

function defaultScope(): ScopeForm {
  const scope = readCurrentScope();
  return { tenant_id: scope.tenant_id, project_id: scope.project_id, environment: scope.environment };
}

async function loadOptions() {
  if (mode === "offline") return;
  const [rolesPage, permissionsPage, tenantsPage] = await Promise.all([
    consoleClient.listAdminCollection("/v1/identity/roles"),
    consoleClient.listAdminCollection("/v1/identity/permissions"),
    consoleClient.listAdminCollection("/v1/identity/tenants"),
  ]);
  roleOptions.value = rolesPage.items;
  permissionOptions.value = permissionsPage.items;
  tenantOptions.value = tenantsPage.items;
  await Promise.all(form.allowed_scopes.map((scope) => loadScopeProjects(scope).then(() => loadScopeEnvironments(scope))));
}

async function loadScopeProjects(scope: ScopeForm) {
  if (!scope.tenant_id || projectOptionsByTenant.value[scope.tenant_id]) return;
  projectOptionsByTenant.value[scope.tenant_id] = (await consoleClient.listAdminCollection("/v1/identity/projects", { tenant_id: scope.tenant_id })).items;
}

async function loadScopeEnvironments(scope: ScopeForm) {
  if (!scope.tenant_id || !scope.project_id) return;
  const key = scopeKey(scope);
  if (environmentOptionsByScope.value[key]) return;
  environmentOptionsByScope.value[key] = (
    await consoleClient.listAdminCollection("/v1/identity/environments", {
      tenant_id: scope.tenant_id,
      project_id: scope.project_id,
    })
  ).items;
}

async function onScopeTenantChange(scope: ScopeForm) {
  await loadScopeProjects(scope);
  scope.project_id = projectOptionsFor(scope.tenant_id)[0]?.id || "";
  await loadScopeEnvironments(scope);
  scope.environment = String(environmentOptionsFor(scope.tenant_id, scope.project_id)[0]?.environment || "");
}

function projectOptionsFor(tenantId: string): AdminResource[] {
  return projectOptionsByTenant.value[tenantId] || [];
}

function environmentOptionsFor(tenantId: string, projectId: string): AdminResource[] {
  return environmentOptionsByScope.value[`${tenantId}:${projectId}`] || [];
}

function scopeKey(scope: ScopeForm): string {
  return `${scope.tenant_id}:${scope.project_id}`;
}

function addScope() {
  form.allowed_scopes.push(defaultScope());
}

function removeScope(index: number) {
  form.allowed_scopes.splice(index, 1);
}

function openPasswordDrawer(operator: ConsoleOperator) {
  passwordOperator.value = operator;
  passwordForm.new_password = "";
  mutationError.value = null;
  passwordDrawerOpen.value = true;
}

function closePasswordDrawer() {
  passwordDrawerOpen.value = false;
  passwordOperator.value = null;
  mutationError.value = null;
}

async function resetPassword() {
  if (!passwordOperator.value) return;
  saving.value = true;
  mutationError.value = null;
  try {
    await consoleClient.resetOperatorPassword(passwordOperator.value.id, passwordForm.new_password);
    closePasswordDrawer();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

async function revokeSessions(operator: ConsoleOperator) {
  openConfirm({
    title: "撤销操作员会话",
    message: `撤销 ${operator.email} 的所有有效会话。`,
    warning: "该操作会让此操作员已登录的控制台立即失效。",
    items: [
      { label: t("email"), value: operator.email },
      { label: t("status"), value: String(operator.status || "active") },
    ],
    action: async () => {
      await consoleClient.revokeOperatorSessions(operator.id);
      if (editingOperator.value?.id === operator.id) await reloadEditingSessions();
    },
  });
}

async function deleteOperator(operator: ConsoleOperator) {
  openConfirm({
    title: "删除操作员",
    message: `删除操作员 ${operator.email}。`,
    warning: "操作员会被软删除，所有会话会被撤销，后续不能再登录。",
    items: [
      { label: t("name"), value: operator.name },
      { label: t("email"), value: operator.email },
      { label: t("roles"), value: listValue(operator.roles) },
    ],
    action: async () => {
      const deleted = await consoleClient.deleteOperator(operator.id);
      operators.value = operators.value.filter((item) => item.id !== deleted.id);
      if (editingOperator.value?.id === operator.id) closeDrawer();
    },
  });
}

async function reloadEditingSessions() {
  if (!editingOperator.value) return;
  sessionLoading.value = true;
  mutationError.value = null;
  try {
    sessions.value = (await consoleClient.listOperatorSessions(editingOperator.value.id)).items;
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    sessionLoading.value = false;
  }
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
  saving.value = true;
  mutationError.value = null;
  try {
    await confirmState.action();
    closeConfirm();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : "-";
}

function scopeValue(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return "-";
  return value.map((scope) => {
    const record = scope as Record<string, unknown>;
    return `${record.tenant_id}/${record.project_id}/${record.environment}`;
  }).join(", ");
}

onMounted(() => {
  resetForm();
  loadOperators();
});
</script>

<style scoped>
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 280px;
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
  width: min(560px, 100%);
  grid-template-rows: auto 1fr;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.drawer.narrow {
  width: min(420px, 100%);
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

.field {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.scope-editor {
  display: grid;
  gap: 10px;
}

.session-panel {
  display: grid;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 36%, transparent);
  padding: 12px;
}

.session-list {
  display: grid;
  gap: 8px;
  max-height: 260px;
  overflow: auto;
}

.session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px 10px;
  border-bottom: 1px solid var(--color-border);
  padding: 8px 0;
}

.session-row small {
  color: var(--color-text-muted);
  overflow-wrap: anywhere;
}

.scope-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.scope-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 48%, transparent);
  padding: 12px;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  margin: 8px -18px -18px;
  padding: 14px 18px;
}

.permission-fieldset {
  display: grid;
  max-height: 260px;
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

@media (max-width: 920px) {
  .drawer {
    width: 100%;
  }

  .scope-grid {
    grid-template-columns: 1fr;
  }
}
</style>
