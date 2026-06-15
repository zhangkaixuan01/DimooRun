<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("rolePermissionMatrix") }}</h1>
        <p class="page-subtitle">{{ t("rolePermissionMatrixCopy") }}</p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && roles.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && roles.length > 0" class="matrix-layout">
      <aside class="role-list panel">
        <div class="list-header">
          <input v-model.trim="roleQuery" class="input" :placeholder="t('searchRoles')" :aria-label="t('searchRoles')" />
        </div>
        <button
          v-for="role in filteredRoles"
          :key="role.id"
          class="role-row"
          :class="{ active: selectedRole?.id === role.id }"
          type="button"
          @click="selectRole(role)"
        >
          <strong>{{ role.name }}</strong>
          <span>{{ permissionCount(role) }} {{ t("permissionsCount") }}</span>
        </button>
      </aside>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("roleMatrix") }}</p>
            <h2 class="panel-title">{{ selectedRole?.name || t("role") }}</h2>
            <p class="muted">{{ t("roleMatrixCopy") }}</p>
          </div>
          <div class="panel-actions">
            <button class="button" type="button" :disabled="!selectedRole || previewLoading" @click="refreshPreview">
              {{ previewLoading ? t("loading") : t("previewImpact") }}
            </button>
            <button class="button primary" type="button" :disabled="saveDisabled" @click="applyMatrix">
              {{ saving ? t("loading") : t("applyMatrix") }}
            </button>
          </div>
        </header>

        <div class="toolbar">
          <input v-model.trim="permissionQuery" class="input" :placeholder="t('searchPermissions')" :aria-label="t('searchPermissions')" />
          <label class="audit-field">
            <span>{{ t("auditReason") }}</span>
            <input v-model.trim="auditReason" class="input" :placeholder="t('explainRoleChange')" :aria-label="t('auditReason')" />
          </label>
        </div>

        <p v-if="saveDisabledReason" class="form-error">{{ saveDisabledReason }}</p>
        <InlineApiError :error="mutationError" />

        <div class="matrix-grid">
          <section class="permission-panel">
            <section v-for="group in groupedPermissions" :key="group.resource" class="permission-group">
              <h3>{{ group.resource }}</h3>
              <div class="permission-grid">
                <label v-for="permission in group.items" :key="permission.id" class="permission-row">
                  <input
                    v-model="selectedPermissionCodes"
                    type="checkbox"
                    :value="String(permission.code || permission.name)"
                    :disabled="!selectedRole || saving"
                  />
                  <span>
                    <strong class="mono">{{ permission.code || permission.name }}</strong>
                    <small>{{ permission.resource || "-" }} / {{ permission.action || "-" }}</small>
                  </span>
                </label>
              </div>
            </section>
          </section>

          <aside class="preview-panel">
            <header class="preview-header">
              <div>
                <p class="section-kicker">{{ t("effectivePermissionPreview") }}</p>
                <h3>{{ t("changeSummary") }}</h3>
              </div>
            </header>

            <div v-if="preview" class="preview-body">
              <dl class="diff-grid">
                <div>
                  <dt>{{ t("added") }}</dt>
                  <dd>{{ preview.change.added.length }}</dd>
                </div>
                <div>
                  <dt>{{ t("removed") }}</dt>
                  <dd>{{ preview.change.removed.length }}</dd>
                </div>
                <div>
                  <dt>{{ t("affectedOperators") }}</dt>
                  <dd>{{ preview.affected_operators.length }}</dd>
                </div>
              </dl>

              <section class="delta-section">
                <h4>{{ t("permissionDiff") }}</h4>
                <p class="delta-row">
                  <strong>{{ t("added") }}:</strong>
                  <span>{{ listOrDash(preview.change.added) }}</span>
                </p>
                <p class="delta-row">
                  <strong>{{ t("removed") }}:</strong>
                  <span>{{ listOrDash(preview.change.removed) }}</span>
                </p>
              </section>

              <section v-if="preview.warnings.length > 0" class="delta-section">
                <h4>{{ t("warnings") }}</h4>
                <article v-for="(warning, index) in preview.warnings" :key="index" class="warning-card">
                  <strong>{{ warning.code || "warning" }}</strong>
                  <p>{{ warning.message || "-" }}</p>
                </article>
              </section>

              <section class="delta-section">
                <h4>{{ t("affectedOperators") }}</h4>
                <div v-if="preview.affected_operators.length === 0" class="muted">{{ t("noOperatorsAssignedToRole") }}</div>
                <article
                  v-for="operator in preview.affected_operators"
                  :key="operator.operator_id"
                  class="impact-row"
                >
                  <strong>{{ operator.email }}</strong>
                  <small>{{ operator.name }}</small>
                  <span class="mono">
                    {{ operator.current_permissions?.length || 0 }} -> {{ operator.preview_permissions?.length || 0 }}
                  </span>
                </article>
              </section>
            </div>
            <p v-else class="muted">{{ t("selectRolePreviewCopy") }}</p>
          </aside>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type AdminResource,
  type ConsoleApiError,
  type RolePermissionPreview,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const loading = ref(false);
const previewLoading = ref(false);
const saving = ref(false);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const roles = ref<AdminResource[]>([]);
const permissions = ref<AdminResource[]>([]);
const selectedRole = ref<AdminResource | null>(null);
const selectedPermissionCodes = ref<string[]>([]);
const roleQuery = ref("");
const permissionQuery = ref("");
const auditReason = ref("");
const preview = ref<RolePermissionPreview | null>(null);

const filteredRoles = computed(() => {
  const query = roleQuery.value.toLowerCase();
  if (!query) return roles.value;
  return roles.value.filter((role) =>
    [role.name, role.description, role.id].map((value) => String(value || "").toLowerCase()).some((value) => value.includes(query)),
  );
});
const filteredPermissions = computed(() => {
  const query = permissionQuery.value.toLowerCase();
  if (!query) return permissions.value;
  return permissions.value.filter((permission) =>
    [permission.code, permission.name, permission.resource, permission.action]
      .map((value) => String(value || "").toLowerCase())
      .some((value) => value.includes(query)),
  );
});
const groupedPermissions = computed(() => {
  const groups = new Map<string, AdminResource[]>();
  for (const permission of filteredPermissions.value) {
    const resource = String(permission.resource || String(permission.code || permission.name).split(":")[0] || "other");
    groups.set(resource, [...(groups.get(resource) || []), permission]);
  }
  return [...groups.entries()].map(([resource, items]) => ({ resource, items }));
});
const previewHasSelfLockout = computed(() =>
  preview.value?.warnings.some((warning) => String(warning.code || "") === "self_lockout_risk") ?? false,
);
const saveDisabledReason = computed(() => {
  if (!selectedRole.value) return t("selectRoleFirst");
  if (previewHasSelfLockout.value) return t("roleSelfLockoutWarning");
  if (!auditReason.value.trim()) return t("auditReasonRequired");
  return "";
});
const saveDisabled = computed(() => !selectedRole.value || saving.value || previewLoading.value || Boolean(saveDisabledReason.value));

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const response = await consoleClient.getRolePermissionMatrix();
    roles.value = response.items;
    permissions.value = response.permissions;
    if (roles.value.length > 0) {
      selectRole(roles.value[0]);
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function selectRole(role: AdminResource) {
  selectedRole.value = role;
  selectedPermissionCodes.value = Array.isArray(role.permissions) ? role.permissions.map(String) : [];
  preview.value = null;
  mutationError.value = null;
  void refreshPreview();
}

async function refreshPreview() {
  if (!selectedRole.value) return;
  previewLoading.value = true;
  mutationError.value = null;
  try {
    preview.value = await consoleClient.previewRoleMatrix(selectedRole.value.id, selectedPermissionCodes.value);
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    previewLoading.value = false;
  }
}

async function applyMatrix() {
  if (!selectedRole.value || saveDisabled.value) return;
  saving.value = true;
  mutationError.value = null;
  try {
    preview.value = await consoleClient.applyRoleMatrix(selectedRole.value.id, selectedPermissionCodes.value, auditReason.value);
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

function permissionCount(role: AdminResource): number {
  return Array.isArray(role.permissions) ? role.permissions.length : 0;
}

function listOrDash(value: string[]): string {
  return value.length > 0 ? value.join(", ") : "-";
}

watch(
  () => selectedPermissionCodes.value.join("|"),
  () => {
    if (selectedRole.value) {
      void refreshPreview();
    }
  },
);

onMounted(load);
</script>

<style scoped>
.matrix-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 14px;
}

.panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.role-list {
  overflow: hidden;
}

.list-header,
.toolbar {
  padding: 14px;
  border-bottom: 1px solid var(--color-border);
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 260px) minmax(260px, 1fr);
  gap: 12px;
}

.audit-field {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.role-row {
  display: grid;
  gap: 4px;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  padding: 12px 14px;
  text-align: left;
}

.role-row.active {
  background: var(--color-accent-soft);
}

.role-row span,
.muted,
.permission-row small,
.impact-row small {
  color: var(--color-text-muted);
  font-size: 12px;
}

.panel-header,
.preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-bottom: 1px solid var(--color-border);
}

.panel-title {
  margin: 0;
}

.panel-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.matrix-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.9fr);
  min-height: 560px;
}

.permission-panel {
  border-right: 1px solid var(--color-border);
}

.permission-group h3,
.preview-header h3,
.delta-section h4 {
  margin: 0;
}

.permission-group h3 {
  padding: 14px 14px 0;
  color: var(--color-text-muted);
  font-size: 12px;
  text-transform: uppercase;
}

.permission-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
  padding: 14px;
}

.permission-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

.permission-row span {
  display: grid;
  gap: 3px;
}

.preview-panel {
  display: grid;
  grid-template-rows: auto 1fr;
}

.preview-body {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 14px;
}

.diff-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.diff-grid div,
.warning-card,
.impact-row {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 52%, transparent);
  padding: 10px;
}

.diff-grid dt {
  color: var(--color-text-muted);
  font-size: 12px;
}

.diff-grid dd {
  margin: 6px 0 0;
  font-size: 20px;
  font-weight: 700;
}

.delta-section {
  display: grid;
  gap: 8px;
}

.delta-row {
  display: grid;
  gap: 4px;
  margin: 0;
}

.warning-card p,
.impact-row {
  margin: 4px 0 0;
}

.impact-row {
  display: grid;
  gap: 4px;
}

@media (max-width: 1100px) {
  .matrix-layout,
  .matrix-grid {
    grid-template-columns: 1fr;
  }

  .permission-panel {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
