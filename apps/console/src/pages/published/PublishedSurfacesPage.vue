<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("publishedKicker") }}</p>
        <h1 class="page-title">{{ t("publishedSurfaces") }}</h1>
        <p class="page-subtitle">{{ t("publishedCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || !canWrite" @click="openCreateSurface">
        {{ t("createPublishedSurface") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && surfaces.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && surfaces.length > 0" class="table-wrap surfaces-table">
      <table>
        <thead>
          <tr>
            <th>{{ t("surface") }}</th>
            <th>deployment_id</th>
            <th>{{ t("type") }}</th>
            <th>{{ t("status") }}</th>
            <th>{{ t("routeCount") }}</th>
            <th>{{ t("createdAt") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="surface in surfaces"
            :key="surface.id"
            class="surface-row"
            :class="{ selected: selectedSurface?.id === surface.id }"
            :data-selected="selectedSurface?.id === surface.id ? 'true' : 'false'"
            tabindex="0"
            :aria-selected="selectedSurface?.id === surface.id"
            @click="selectSurface(surface)"
            @keydown.enter="selectSurface(surface)"
            @keydown.space.prevent="selectSurface(surface)"
          >
            <td>
              <strong>{{ resourceName(surface) }}</strong><br />
              <span class="mono muted">{{ surface.id }}</span>
            </td>
            <td class="mono">{{ surface.deployment_id }}</td>
            <td>{{ surface.type || "http" }}</td>
            <td><StatusBadge :status="String(surface.status || 'active')" :label="String(surface.status || 'active')" /></td>
            <td>{{ routesForSurface(surface.id).length }}</td>
            <td>{{ formatDateTime(surface.created_at) }}</td>
            <td class="actions-cell">
              <button class="button" type="button" :disabled="!canWrite || mutatingId === surface.id" @click.stop="openEdit('surface', surface)">{{ t("edit") }}</button>
              <button class="button" type="button" :disabled="!canWrite || mutatingId === surface.id" @click.stop="toggleStatus('surface', surface)">
                {{ surface.status === "disabled" ? t("enable") : t("disable") }}
              </button>
              <button class="button danger" type="button" :disabled="!canWrite || mutatingId === surface.id" @click.stop="openDelete('surface', surface)">{{ t("delete") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="mode !== 'offline' && !loading && !error && selectedSurface" class="panel publish-detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">{{ t("surface") }}</p>
          <h2 class="panel-title">{{ resourceName(selectedSurface) }}</h2>
          <p class="muted">Deployment #{{ selectedSurface.deployment_id }} / {{ selectedSurface.type || "http" }}</p>
        </div>
        <div class="detail-actions">
          <button class="button primary" type="button" :disabled="!canWrite || selectedSurface.status === 'disabled'" @click="showRouteForm = true">
            {{ t("addIngressRoute") }}
          </button>
          <button class="button" type="button" :disabled="!canWrite" @click="openEdit('surface', selectedSurface)">{{ t("edit") }}</button>
          <button class="button" type="button" :disabled="!canWrite || mutatingId === selectedSurface.id" @click="toggleStatus('surface', selectedSurface)">
            {{ selectedSurface.status === "disabled" ? t("enable") : t("disable") }}
          </button>
        </div>
      </div>
      <div class="panel-body publish-detail-layout">
        <aside class="surface-summary">
          <dl>
            <div>
              <dt>{{ t("id") }}</dt>
              <dd class="mono">{{ selectedSurface.id }}</dd>
            </div>
            <div>
              <dt>{{ t("status") }}</dt>
              <dd><StatusBadge :status="String(selectedSurface.status || 'active')" :label="String(selectedSurface.status || 'active')" /></dd>
            </div>
            <div>
              <dt>deployment_id</dt>
              <dd class="mono">{{ selectedSurface.deployment_id }}</dd>
            </div>
            <div>
              <dt>{{ t("routeCount") }}</dt>
              <dd class="metric">{{ selectedRoutes.length }}</dd>
            </div>
          </dl>
        </aside>

        <div class="child-workspace">
          <header class="child-panel-header">
            <div>
              <p class="section-kicker">{{ t("ingressRoutes") }}</p>
              <h3>{{ t("routeInventory") }}</h3>
            </div>
            <button class="button" type="button" :disabled="!canWrite || selectedSurface.status === 'disabled'" @click="showRouteForm = !showRouteForm">
              {{ showRouteForm ? t("hideForm") : t("addIngressRoute") }}
            </button>
          </header>

          <form v-if="showRouteForm" class="nested-form" @submit.prevent="createRoute">
            <div class="form-grid">
              <label>
                <span>{{ t("name") }}</span>
                <input v-model="routeForm.name" class="input" required />
              </label>
              <label>
                <span>{{ t("path") }}</span>
                <input v-model="routeForm.path" class="input" required placeholder="/support" />
              </label>
              <label>
                <span>{{ t("auth") }}</span>
                <input v-model="routeForm.auth_mode" class="input" required />
              </label>
              <label>
                <span>custom_domain</span>
                <input v-model="routeForm.custom_domain" class="input" />
              </label>
            </div>
            <div class="nested-form-actions">
              <button class="button" type="button" @click="closeRouteForm">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingRoute || !canCreateRoute">
                {{ creatingRoute ? t("creating") : t("addIngressRoute") }}
              </button>
            </div>
          </form>

          <div class="table-wrap embedded" v-if="selectedRoutes.length > 0">
            <table>
              <thead>
                <tr>
                  <th>{{ t("path") }}</th>
                  <th>{{ t("auth") }}</th>
                  <th>custom_domain</th>
                  <th>{{ t("status") }}</th>
                  <th>{{ t("actions") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="route in selectedRoutes" :key="route.id">
                  <td class="mono">{{ route.path }}</td>
                  <td>{{ route.auth_mode }}</td>
                  <td>{{ route.custom_domain || "-" }}</td>
                  <td><StatusBadge :status="String(route.status || 'active')" :label="String(route.status || 'active')" /></td>
                  <td class="actions-cell">
                    <button class="button" type="button" :disabled="!canWrite || mutatingId === route.id" @click="openEdit('route', route)">{{ t("edit") }}</button>
                    <button class="button" type="button" :disabled="!canWrite || mutatingId === route.id" @click="toggleStatus('route', route)">
                      {{ route.status === "disabled" ? t("enable") : t("disable") }}
                    </button>
                    <button class="button danger" type="button" :disabled="!canWrite || mutatingId === route.id" @click="openDelete('route', route)">{{ t("delete") }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty-child">{{ t("noIngressRoutesYet") }}</p>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="showCreateSurface" class="drawer-layer" @click.self="closeCreateSurface">
        <aside class="drawer" :aria-label="t('createPublishedSurface')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("surface") }}</p>
              <h2>{{ t("createPublishedSurface") }}</h2>
            </div>
          </header>
          <form class="drawer-form" @submit.prevent="createSurface">
            <label>
              <span>{{ t("name") }}</span>
              <input v-model="surfaceForm.name" class="input" required />
            </label>
            <label>
              <span>deployment_id</span>
              <input v-model.number="surfaceForm.deployment_id" class="input" min="1" required type="number" />
            </label>
            <label>
              <span>{{ t("type") }}</span>
              <input v-model="surfaceForm.type" class="input" required />
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeCreateSurface">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingSurface || !canCreateSurface">
                {{ creatingSurface ? t("creating") : t("createPublishedSurface") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="editTarget" class="drawer-layer" @click.self="closeEdit">
        <aside class="drawer wide-drawer" :aria-label="t('edit')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ editKind === "surface" ? t("surface") : t("ingressRoutes") }}</p>
              <h2>{{ t("edit") }} #{{ editTarget.id }}</h2>
            </div>
          </header>
          <form class="drawer-form" @submit.prevent="saveEdit">
            <label>
              <span>{{ t("payload") }}</span>
              <textarea v-model="editPayloadJson" class="textarea code-input" rows="16"></textarea>
            </label>
            <p v-if="editError" class="form-error">{{ editError }}</p>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeEdit">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="Boolean(editTarget && mutatingId === editTarget.id)">
                {{ editTarget && mutatingId === editTarget.id ? t("saving") : t("save") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <DangerConfirmDialog
      :open="Boolean(deleteTarget)"
      :title="t('confirmDelete')"
      :message="t('confirmDeleteCopy')"
      :items="deleteConfirmItems"
      :confirm-label="t('delete')"
      :cancel-label="t('cancel')"
      :busy-label="t('saving')"
      :busy="Boolean(deleteTarget && mutatingId === deleteTarget.id)"
      :error="deleteError"
      @cancel="closeDelete"
      @confirm="runConfirmedDelete"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";
import { formatDateTime } from "../../utils/dateTime";

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const surfaces = ref<AdminResource[]>([]);
const routes = ref<AdminResource[]>([]);
const selectedSurface = ref<AdminResource | null>(null);
const showCreateSurface = ref(false);
const showRouteForm = ref(false);
const creatingSurface = ref(false);
const creatingRoute = ref(false);
const mutatingId = ref<number | null>(null);
const editTarget = ref<AdminResource | null>(null);
const editKind = ref<"surface" | "route">("surface");
const editPayloadJson = ref("{}");
const editError = ref("");
const deleteTarget = ref<AdminResource | null>(null);
const deleteKind = ref<"surface" | "route">("surface");
const deleteError = ref<ConsoleApiError | null>(null);
const surfaceForm = reactive({ name: "", deployment_id: null as number | null, type: "http" });
const routeForm = reactive({ name: "", path: "", auth_mode: "api_key", custom_domain: "" });

const canWrite = computed(() => auth.can("admin:write"));
const selectedRoutes = computed(() => selectedSurface.value ? routesForSurface(selectedSurface.value.id) : []);
const canCreateSurface = computed(() => Boolean(surfaceForm.name.trim() && surfaceForm.deployment_id && surfaceForm.type.trim()));
const canCreateRoute = computed(() => Boolean(
  selectedSurface.value
  && selectedSurface.value.status !== "disabled"
  && routeForm.name.trim()
  && routeForm.path.trim()
  && routeForm.auth_mode.trim(),
));
const deleteConfirmItems = computed(() => deleteTarget.value ? [
  { label: t("id"), value: String(deleteTarget.value.id) },
  { label: t("name"), value: resourceName(deleteTarget.value) },
  { label: t("status"), value: String(deleteTarget.value.status || "-") },
] : []);

async function loadPublishing() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [surfacePage, routePage] = await Promise.all([
      consoleClient.listAdminCollection("/v1/published-surfaces"),
      consoleClient.listAdminCollection("/v1/ingress-routes"),
    ]);
    surfaces.value = surfacePage.items;
    routes.value = routePage.items;
    if (!selectedSurface.value && surfaces.value[0]) {
      selectSurface(surfaces.value[0]);
    } else if (selectedSurface.value) {
      selectedSurface.value = surfaces.value.find((item) => item.id === selectedSurface.value?.id) ?? surfaces.value[0] ?? null;
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function selectSurface(surface: AdminResource) {
  selectedSurface.value = surface;
  closeRouteForm();
}

function routesForSurface(surfaceId: number): AdminResource[] {
  return routes.value.filter((route) => Number(route.surface_id) === surfaceId);
}

function resourceName(item: AdminResource): string {
  return String(item.name || item.label || item.path || `#${item.id}`);
}

function openCreateSurface() {
  surfaceForm.name = "";
  surfaceForm.deployment_id = null;
  surfaceForm.type = "http";
  showCreateSurface.value = true;
}

function closeCreateSurface() {
  if (creatingSurface.value) return;
  showCreateSurface.value = false;
}

async function createSurface() {
  if (!canCreateSurface.value || !surfaceForm.deployment_id) return;
  creatingSurface.value = true;
  error.value = null;
  try {
    const surface = await consoleClient.createAdminItem("/v1/published-surfaces", {
      name: surfaceForm.name,
      deployment_id: surfaceForm.deployment_id,
      type: surfaceForm.type,
    });
    surfaces.value = [surface, ...surfaces.value.filter((item) => item.id !== surface.id)];
    selectSurface(surface);
    showCreateSurface.value = false;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingSurface.value = false;
  }
}

function closeRouteForm() {
  showRouteForm.value = false;
  routeForm.name = "";
  routeForm.path = "";
  routeForm.auth_mode = "api_key";
  routeForm.custom_domain = "";
}

async function createRoute() {
  if (!selectedSurface.value || !canCreateRoute.value) return;
  creatingRoute.value = true;
  error.value = null;
  try {
    const route = await consoleClient.createAdminItem("/v1/ingress-routes", {
      name: routeForm.name,
      surface_id: selectedSurface.value.id,
      path: routeForm.path,
      auth_mode: routeForm.auth_mode,
      custom_domain: routeForm.custom_domain || undefined,
    });
    routes.value = [route, ...routes.value.filter((item) => item.id !== route.id)];
    closeRouteForm();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingRoute.value = false;
  }
}

function openEdit(kind: "surface" | "route", item: AdminResource) {
  editKind.value = kind;
  editTarget.value = item;
  editError.value = "";
  editPayloadJson.value = JSON.stringify(editPayloadFor(item), null, 2);
}

function closeEdit() {
  editTarget.value = null;
  editPayloadJson.value = "{}";
  editError.value = "";
}

function editPayloadFor(item: AdminResource): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(item)) {
    if (["id", "created_at", "created_by", "updated_at", "updated_by", "deleted_at", "deleted_by", "is_deleted"].includes(key)) continue;
    payload[key] = value;
  }
  return payload;
}

async function saveEdit() {
  if (!editTarget.value) return;
  const payload = parseEditPayload();
  if (!payload) return;
  const path = editKind.value === "surface" ? "/v1/published-surfaces" : "/v1/ingress-routes";
  mutatingId.value = editTarget.value.id;
  error.value = null;
  try {
    const updated = await consoleClient.updateAdminItem(path, editTarget.value.id, payload);
    replaceResource(editKind.value, updated);
    closeEdit();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
}

async function toggleStatus(kind: "surface" | "route", item: AdminResource) {
  const path = kind === "surface" ? "/v1/published-surfaces" : "/v1/ingress-routes";
  mutatingId.value = item.id;
  error.value = null;
  try {
    const updated = await consoleClient.updateAdminItem(path, item.id, {
      ...editPayloadFor(item),
      status: item.status === "disabled" ? "active" : "disabled",
    });
    replaceResource(kind, updated);
    if (kind === "surface" && updated.status === "disabled") {
      closeRouteForm();
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
}

function parseEditPayload(): Record<string, unknown> | null {
  editError.value = "";
  try {
    const parsed = JSON.parse(editPayloadJson.value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      editError.value = t("jsonObjectRequired");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    editError.value = t("invalidJson");
    return null;
  }
}

function openDelete(kind: "surface" | "route", item: AdminResource) {
  deleteKind.value = kind;
  deleteTarget.value = item;
  deleteError.value = null;
}

function closeDelete() {
  if (deleteTarget.value && mutatingId.value === deleteTarget.value.id) return;
  deleteTarget.value = null;
  deleteError.value = null;
}

async function runConfirmedDelete() {
  if (!deleteTarget.value) return;
  const path = deleteKind.value === "surface" ? "/v1/published-surfaces" : "/v1/ingress-routes";
  mutatingId.value = deleteTarget.value.id;
  deleteError.value = null;
  try {
    const deleted = await consoleClient.deleteAdminItem(path, deleteTarget.value.id);
    if (deleteKind.value === "surface") {
      surfaces.value = surfaces.value.filter((item) => item.id !== deleted.id);
      if (selectedSurface.value?.id === deleted.id) selectedSurface.value = surfaces.value[0] ?? null;
    } else {
      routes.value = routes.value.filter((item) => item.id !== deleted.id);
    }
    deleteTarget.value = null;
  } catch (caught) {
    deleteError.value = toConsoleApiError(caught);
  } finally {
    mutatingId.value = null;
  }
}

function replaceResource(kind: "surface" | "route", updated: AdminResource) {
  if (kind === "surface") {
    surfaces.value = surfaces.value.map((item) => item.id === updated.id ? updated : item);
    if (selectedSurface.value?.id === updated.id) selectedSurface.value = updated;
    return;
  }
  routes.value = routes.value.map((item) => item.id === updated.id ? updated : item);
}

onMounted(loadPublishing);
</script>

<style scoped>
.surfaces-table tbody tr.surface-row {
  cursor: pointer;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.surfaces-table tbody tr.surface-row td {
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.surfaces-table tbody tr.surface-row:hover,
.surfaces-table tbody tr.surface-row:focus-visible {
  background: color-mix(in oklab, var(--color-primary) 8%, transparent);
  outline: none;
}

.surfaces-table tbody tr.surface-row.selected,
.surfaces-table tbody tr.surface-row[data-selected="true"] {
  background: var(--color-accent-soft);
}

.surfaces-table tbody tr.surface-row.selected td,
.surfaces-table tbody tr.surface-row[data-selected="true"] td {
  background: var(--color-accent-soft) !important;
}

.surfaces-table tbody tr.surface-row.selected td:first-child,
.surfaces-table tbody tr.surface-row[data-selected="true"] td:first-child {
  box-shadow: inset 3px 0 0 var(--color-primary) !important;
}

.actions-cell,
.detail-actions,
.nested-form-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.publish-detail-panel {
  margin-top: 16px;
}

.section-kicker {
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0;
  margin: 0 0 4px;
  text-transform: uppercase;
}

.publish-detail-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 16px;
}

.surface-summary {
  border-right: 1px solid var(--color-border);
  padding-right: 16px;
}

.surface-summary dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

.surface-summary dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.surface-summary dd {
  margin: 0;
}

.metric {
  font-size: 1.35rem;
  font-weight: 800;
}

.child-workspace {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.child-panel-header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.child-panel-header h3 {
  margin: 0;
  font-size: 1rem;
}

.nested-form {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.embedded {
  margin: 0;
}

.empty-child {
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-text-muted);
  margin: 0;
  padding: 18px;
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

.wide-drawer {
  width: min(640px, 100%);
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

.textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  padding: 10px 12px;
  font: inherit;
}

.code-input {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
}

.form-error {
  margin: 0;
  color: var(--color-danger);
  font-weight: 700;
}

@media (max-width: 900px) {
  .publish-detail-layout,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .surface-summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 14px;
  }

  .drawer {
    width: 100%;
  }
}
</style>
