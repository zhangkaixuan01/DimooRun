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
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div v-if="showCreate" class="drawer-layer" @click.self="closeCreateDrawer">
        <aside class="drawer" :aria-label="t('create')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("identity") }}</p>
              <h2>{{ t("create") }} {{ t("operators") }}</h2>
            </div>
            <button class="button" type="button" @click="closeCreateDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="createOperator">
            <label class="field">
              {{ t("name") }}
              <input v-model="form.name" class="input" required placeholder="Ops Operator" />
            </label>
            <label class="field">
              {{ t("email") }}
              <input v-model="form.email" class="input" autocomplete="username" required type="email" />
            </label>
            <label class="field">
              {{ t("initialPassword") }}
              <input v-model="form.password" class="input" autocomplete="new-password" required type="password" />
            </label>
            <label class="field">
              {{ t("roles") }}
              <input v-model="form.roles" class="input" required placeholder="runtime_operator" />
            </label>
            <label class="field">
              {{ t("permissions") }}
              <input v-model="form.permissions" class="input" required placeholder="agent:read, run:read" />
            </label>
            <div class="scope-grid">
              <label class="field">
                {{ t("tenant") }}
                <input v-model="form.tenant_id" class="input" required />
              </label>
              <label class="field">
                {{ t("project") }}
                <input v-model="form.project_id" class="input" required />
              </label>
              <label class="field">
                {{ t("environment") }}
                <input v-model="form.environment" class="input" required />
              </label>
            </div>
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
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError, type ConsoleOperator } from "../../api/client";
import { readCurrentScope } from "../../api/scope";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const canManageOperators = computed(() => auth.can("identity:operator:write"));
const loading = ref(false);
const creating = ref(false);
const showCreate = ref(false);
const error = ref<ConsoleApiError | null>(null);
const operators = ref<ConsoleOperator[]>([]);
const form = reactive({
  name: "",
  email: "",
  password: "",
  roles: "runtime_operator",
  permissions: "agent:read, run:read",
  tenant_id: "",
  project_id: "",
  environment: "",
});

async function loadOperators() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const page = (await consoleClient.listAdminCollection("/v1/identity/operators")) as unknown as {
      items: ConsoleOperator[];
    };
    operators.value = page.items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createOperator() {
  creating.value = true;
  error.value = null;
  try {
    const operator = (await consoleClient.createAdminItem("/v1/identity/operators", {
      email: form.email.trim(),
      name: form.name.trim(),
      password: form.password,
      roles: csv(form.roles),
      permissions: csv(form.permissions),
      allowed_scopes: [
        {
          tenant_id: form.tenant_id.trim(),
          project_id: form.project_id.trim(),
          environment: form.environment.trim(),
        },
      ],
    })) as ConsoleOperator;
    operators.value = [operator, ...operators.value];
    closeCreateDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function openCreateDrawer() {
  if (!canManageOperators.value) return;
  resetForm();
  showCreate.value = true;
}

function closeCreateDrawer() {
  showCreate.value = false;
  resetForm();
}

function resetForm() {
  const scope = readCurrentScope();
  form.name = "";
  form.email = "";
  form.password = "";
  form.roles = "runtime_operator";
  form.permissions = "agent:read, run:read";
  form.tenant_id = scope.tenant_id;
  form.project_id = scope.project_id;
  form.environment = scope.environment;
}

function csv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : "-";
}

function scopeValue(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return "-";
  return value
    .map((scope) => {
      const record = scope as Record<string, unknown>;
      return `${record.tenant_id}/${record.project_id}/${record.environment}`;
    })
    .join(", ");
}

onMounted(() => {
  resetForm();
  loadOperators();
});
</script>

<style scoped>
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

.scope-grid {
  display: grid;
  grid-template-columns: 1fr;
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

@media (max-width: 920px) {
  .drawer {
    width: 100%;
  }
}
</style>
