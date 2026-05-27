<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("rolesPermissions") }}</h1>
        <p class="page-subtitle">{{ t("rolesPermissionsCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canWrite" @click="openRoleDrawer">
        {{ t("create") }} {{ t("roles") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && roles.length === 0 && permissions.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error" class="role-layout">
      <aside class="role-list">
        <button v-for="role in roles" :key="role.id" class="role-row" :class="{ active: selectedRole?.id === role.id }" type="button" @click="selectedRole = role">
          <strong>{{ role.name }}</strong>
          <span>{{ permissionCount(role) }} {{ t("permissions") }}</span>
        </button>
      </aside>

      <section class="matrix">
        <header class="matrix-header">
          <div>
            <h2>{{ selectedRole?.name || t("roles") }}</h2>
            <p>{{ t("permissionCatalogCopy") }}</p>
          </div>
          <button class="button primary" type="button" :disabled="!selectedRole || !canWrite || saving" @click="saveRolePermissions">
            {{ saving ? t("loading") : t("save") }}
          </button>
        </header>
        <div class="permission-grid">
          <label v-for="permission in permissions" :key="permission.id" class="permission-row">
            <input v-model="selectedPermissionCodes" type="checkbox" :value="permission.code || permission.name" :disabled="!selectedRole || !canWrite" />
            <span>
              <strong class="mono">{{ permission.code || permission.name }}</strong>
              <small>{{ permission.resource || "-" }} / {{ permission.action || "-" }}</small>
            </span>
          </label>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="roleDrawerOpen" class="drawer-layer" @click.self="closeRoleDrawer">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("rolesPermissions") }}</p>
              <h2>{{ t("create") }} {{ t("roles") }}</h2>
            </div>
            <button class="button" type="button" @click="closeRoleDrawer">{{ t("cancel") }}</button>
          </header>
          <form class="drawer-form" @submit.prevent="createRole">
            <label class="field">
              {{ t("name") }}
              <input v-model="roleForm.name" class="input" required placeholder="platform-operator" />
            </label>
            <label class="field">
              {{ t("description") }}
              <textarea v-model="roleForm.description" class="input" rows="4" />
            </label>
            <fieldset class="permission-fieldset">
              <legend>{{ t("permissions") }}</legend>
              <label v-for="permission in permissions" :key="permission.id" class="permission-row compact">
                <input v-model="roleForm.permissions" type="checkbox" :value="permission.code || permission.name" />
                <span>
                  <strong class="mono">{{ permission.code || permission.name }}</strong>
                  <small>{{ permission.resource || "-" }} / {{ permission.action || "-" }}</small>
                </span>
              </label>
            </fieldset>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeRoleDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingRole">{{ creatingRole ? t("creating") : t("save") }}</button>
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
import ApiState from "../../components/ApiState.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const roles = ref<AdminResource[]>([]);
const permissions = ref<AdminResource[]>([]);
const selectedRole = ref<AdminResource | null>(null);
const selectedPermissionCodes = ref<string[]>([]);
const loading = ref(false);
const saving = ref(false);
const creatingRole = ref(false);
const roleDrawerOpen = ref(false);
const error = ref<ConsoleApiError | null>(null);
const roleForm = reactive({ name: "", description: "", permissions: [] as string[] });
const canWrite = computed(() => auth.can("identity:role:write"));

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [rolesPage, permissionsPage] = await Promise.all([
      consoleClient.listAdminCollection("/v1/identity/roles"),
      consoleClient.listAdminCollection("/v1/identity/permissions"),
    ]);
    roles.value = rolesPage.items;
    permissions.value = permissionsPage.items;
    selectedRole.value = roles.value[0] || null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createRole() {
  if (!canWrite.value) return;
  creatingRole.value = true;
  error.value = null;
  try {
    const role = await consoleClient.createAdminItem("/v1/identity/roles", {
      name: roleForm.name,
      description: roleForm.description || null,
    });
    const updated =
      roleForm.permissions.length > 0
        ? await consoleClient.updateAdminItem("/v1/identity/roles", role.id, {
            permissions: roleForm.permissions,
          })
        : role;
    roles.value = [updated, ...roles.value];
    selectedRole.value = updated;
    closeRoleDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingRole.value = false;
  }
}

async function saveRolePermissions() {
  if (!selectedRole.value || !canWrite.value) return;
  saving.value = true;
  error.value = null;
  try {
    const updated = await consoleClient.updateAdminItem("/v1/identity/roles", selectedRole.value.id, {
      permissions: selectedPermissionCodes.value,
    });
    roles.value = roles.value.map((role) => (role.id === updated.id ? updated : role));
    selectedRole.value = updated;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

function permissionCount(role: AdminResource): number {
  return Array.isArray(role.permissions) ? role.permissions.length : 0;
}

function openRoleDrawer() {
  roleForm.name = "";
  roleForm.description = "";
  roleForm.permissions = [];
  roleDrawerOpen.value = true;
}

function closeRoleDrawer() {
  roleDrawerOpen.value = false;
}

watch(selectedRole, (role) => {
  selectedPermissionCodes.value = Array.isArray(role?.permissions) ? [...role.permissions.map(String)] : [];
});

onMounted(load);
</script>

<style scoped>
.role-layout {
  display: grid;
  grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
  gap: 14px;
}

.role-list,
.matrix {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.role-list {
  display: grid;
  align-content: start;
  overflow: hidden;
}

.role-row {
  display: grid;
  gap: 4px;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  padding: 12px;
  text-align: left;
}

.role-row.active {
  background: var(--color-accent-soft);
}

.role-row span,
.matrix-header p,
.permission-row small {
  color: var(--color-text-muted);
  font-size: 12px;
}

.matrix-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px;
}

.matrix-header h2 {
  margin: 0;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 8px;
  padding: 14px;
}

.permission-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

.permission-row.compact {
  border: 0;
  border-bottom: 1px solid var(--color-border);
  border-radius: 0;
}

.permission-row span {
  display: grid;
  gap: 3px;
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
  width: min(520px, 100%);
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
  max-height: 360px;
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

@media (max-width: 900px) {
  .role-layout {
    grid-template-columns: 1fr;
  }
}
</style>
