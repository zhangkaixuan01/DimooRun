<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">{{ t("serviceAccountDetail") }}</h1>
        <p class="page-subtitle">{{ t("serviceAccountDetailCopy") }}</p>
      </div>
      <div class="header-actions">
        <RouterLink class="button" to="/identity/machine-identities">{{ t("backToMachineIdentities") }}</RouterLink>
        <button class="button" type="button" :disabled="busy || !detail" @click="toggleAccountStatus">
          {{ detail?.item.status === "disabled" ? t("enable") : t("disable") }}
        </button>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !detail" />

    <div v-if="mode !== 'offline' && !loading && !error && detail" class="detail-layout">
      <section class="panel hero-panel">
        <div>
          <p class="section-kicker">{{ t("serviceAccount") }}</p>
          <h2 class="panel-title">{{ detail.item.name }}</h2>
          <p class="muted">tenant={{ detail.item.tenant_id }} / project={{ detail.item.project_id ?? "*" }}</p>
        </div>
        <div class="summary-grid">
          <div>
            <span>{{ t("status") }}</span>
            <strong>{{ detail.item.status }}</strong>
          </div>
          <div>
            <span>{{ t("lastUsed") }}</span>
            <strong>{{ formatDateTime(detail.item.last_used_at) }}</strong>
          </div>
          <div>
            <span>{{ t("permissions") }}</span>
            <strong>{{ detail.item.permissions.length }}</strong>
          </div>
          <div>
            <span>{{ t("dependentDeployments") }}</span>
            <strong>{{ detail.item.dependent_deployments.length }}</strong>
          </div>
        </div>
      </section>

      <InlineApiError :error="mutationError" />

      <div v-if="plainKey" class="secret-once">
        <strong>{{ t("serviceOneTimeSecret") }}</strong>
        <code>{{ plainKey }}</code>
      </div>

      <div class="panel-grid">
        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">{{ t("keyCreation") }}</p>
              <h3 class="panel-title">{{ t("createServiceApiKey") }}</h3>
            </div>
          </header>
          <form class="panel-form" @submit.prevent="createKey">
            <label class="field">
              <span>{{ t("name") }}</span>
              <input v-model.trim="createForm.name" class="input" placeholder="runtime-key" required />
            </label>
            <label class="field">
              <span>{{ t("scopes") }}</span>
              <select v-model="createForm.scopes" class="select" multiple>
                <option v-for="permission in detail.item.permissions" :key="permission" :value="permission">{{ permission }}</option>
              </select>
            </label>
            <label class="field">
              <span>{{ t("expires") }}</span>
              <input v-model="createForm.expires_at" class="input" type="datetime-local" />
            </label>
            <div class="form-actions">
              <button class="button primary" type="submit" :disabled="busy || createForm.name.length === 0">{{ t("createKey") }}</button>
            </div>
          </form>
        </section>

        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">{{ t("dependencies") }}</p>
              <h3 class="panel-title">{{ t("publishedSurfacesAndDeployments") }}</h3>
            </div>
          </header>
          <div class="dependency-list">
            <article
              v-for="deployment in detail.item.dependent_deployments"
              :key="String((deployment as Record<string, unknown>).deployment_id || '')"
              class="dependency-row"
            >
              <strong>Deployment #{{ deployment.deployment_id }}</strong>
              <small>agent={{ deployment.agent_id }} / env={{ deployment.environment }}</small>
              <span class="muted">
                {{ surfaceNames(deployment.published_surfaces) }}
              </span>
            </article>
            <p v-if="detail.item.dependent_deployments.length === 0" class="muted">{{ t("noDependentDeployments") }}</p>
          </div>
        </section>
      </div>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="section-kicker">{{ t("apiKeyLifecycle") }}</p>
            <h3 class="panel-title">{{ t("apiKeyLifecycleCopy") }}</h3>
          </div>
        </header>
        <div class="table-wrap embedded">
          <table>
            <thead>
              <tr>
                <th>{{ t("name") }}</th>
                <th>{{ t("prefix") }}</th>
                <th>{{ t("status") }}</th>
                <th>{{ t("lastUsed") }}</th>
                <th>{{ t("scopeDiff") }}</th>
                <th>{{ t("actions") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="key in detail.item.api_keys" :key="key.id">
                <td>
                  <strong>{{ key.name || key.id }}</strong><br />
                  <span class="mono muted">{{ key.id }}</span>
                </td>
                <td class="mono">{{ key.key_prefix || "-" }}</td>
                <td>{{ key.status || "-" }}</td>
                <td>{{ formatDateTime(key.last_used_at) }}</td>
                <td class="scope-cell">
                  <div>{{ t("added") }}: {{ listValue(key.scope_diff?.added) }}</div>
                  <div>{{ t("removed") }}: {{ listValue(key.scope_diff?.removed) }}</div>
                </td>
                <td>
                  <div class="row-actions">
                    <button class="button" type="button" :disabled="busy" @click="openRotate(key)">{{ t("rotateKey") }}</button>
                    <button
                      v-if="key.status === 'disabled'"
                      class="button"
                      type="button"
                      :disabled="busy"
                      @click="enableKey(key.id)"
                    >
                      {{ t("enable") }}
                    </button>
                    <button
                      v-else
                      class="button"
                      type="button"
                      :disabled="busy"
                      @click="disableKey(key.id)"
                    >
                      {{ t("disable") }}
                    </button>
                    <button class="button danger" type="button" :disabled="busy" @click="openExpire(key)">{{ t("forceExpire") }}</button>
                  </div>
                </td>
              </tr>
              <tr v-if="detail.item.api_keys.length === 0">
                <td colspan="6" class="muted">{{ t("noApiKeys") }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="actionDrawerOpen" class="drawer-layer" @click.self="closeActionDrawer">
        <aside class="drawer" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="section-kicker">{{ drawerMode === "rotate" ? t("rotateKey") : t("forceExpire") }}</p>
              <h2>{{ selectedKey?.name || selectedKey?.id }}</h2>
            </div>
          </header>
          <form class="drawer-form" @submit.prevent="submitDrawerAction">
            <template v-if="drawerMode === 'rotate'">
              <label class="field">
                <span>{{ t("newKeyName") }}</span>
                <input v-model.trim="rotateForm.name" class="input" required />
              </label>
              <label class="field">
                <span>{{ t("scopes") }}</span>
                <select v-model="rotateForm.scopes" class="select" multiple>
                  <option v-for="permission in detail?.item.permissions || []" :key="String(permission)" :value="permission">{{ permission }}</option>
                </select>
              </label>
              <label class="field">
                <span>{{ t("expires") }}</span>
                <input v-model="rotateForm.expires_at" class="input" type="datetime-local" />
              </label>
            </template>
            <label class="field">
              <span>{{ t("auditReason") }}</span>
              <input v-model.trim="auditReason" class="input" :placeholder="t('explainCredentialChange')" required />
            </label>
            <div class="form-actions">
              <button class="button" type="button" @click="closeActionDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="busy || auditReason.length === 0">
                {{ drawerMode === "rotate" ? t("rotateKey") : t("forceExpire") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type AdminResource,
  type ConsoleApiError,
  type ServiceAccountDetail,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";

const props = defineProps<{ serviceAccountId: string | number }>();

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const detail = ref<ServiceAccountDetail | null>(null);
const plainKey = ref("");
const actionDrawerOpen = ref(false);
const drawerMode = ref<"rotate" | "expire">("rotate");
const selectedKey = ref<AdminResource | null>(null);
const auditReason = ref("");
const createForm = reactive({
  name: "",
  scopes: [] as string[],
  expires_at: "",
});
const rotateForm = reactive({
  name: "",
  scopes: [] as string[],
  expires_at: "",
});

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    detail.value = await consoleClient.getServiceAccountDetail(Number(props.serviceAccountId));
    if (createForm.scopes.length === 0 && detail.value.item.permissions.length > 0) {
      createForm.scopes = [...detail.value.item.permissions];
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createKey() {
  if (!detail.value) return;
  busy.value = true;
  mutationError.value = null;
  try {
    const response = await consoleClient.createServiceAccountApiKey(detail.value.item.id, {
      name: createForm.name,
      scopes: createForm.scopes,
      expires_at: createForm.expires_at ? new Date(createForm.expires_at).toISOString() : null,
    });
    plainKey.value = response.plain_key;
    createForm.name = "";
    createForm.expires_at = "";
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function toggleAccountStatus() {
  if (!detail.value) return;
  busy.value = true;
  mutationError.value = null;
  try {
    await consoleClient.updateServiceAccount(detail.value.item.id, {
      name: detail.value.item.name,
      tenant_id: detail.value.item.tenant_id,
      project_id: detail.value.item.project_id,
      permissions: detail.value.item.permissions,
      status: detail.value.item.status === "disabled" ? "active" : "disabled",
    });
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function disableKey(keyId: number | string) {
  if (!detail.value) return;
  busy.value = true;
  mutationError.value = null;
  try {
    await consoleClient.disableServiceAccountApiKey(detail.value.item.id, Number(keyId));
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function enableKey(keyId: number | string) {
  if (!detail.value) return;
  busy.value = true;
  mutationError.value = null;
  try {
    await consoleClient.enableServiceAccountApiKey(detail.value.item.id, Number(keyId));
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function openRotate(key: AdminResource) {
  selectedKey.value = key;
  drawerMode.value = "rotate";
  rotateForm.name = `${String(key.name || key.id)}-rotated`;
  rotateForm.scopes = Array.isArray(key.scopes) ? key.scopes.map(String) : [...(detail.value?.item.permissions || [])];
  rotateForm.expires_at = "";
  auditReason.value = "";
  actionDrawerOpen.value = true;
}

function openExpire(key: AdminResource) {
  selectedKey.value = key;
  drawerMode.value = "expire";
  auditReason.value = "";
  actionDrawerOpen.value = true;
}

function closeActionDrawer() {
  actionDrawerOpen.value = false;
  selectedKey.value = null;
}

async function submitDrawerAction() {
  if (!detail.value || !selectedKey.value) return;
  busy.value = true;
  mutationError.value = null;
  try {
    if (drawerMode.value === "rotate") {
      const response = await consoleClient.rotateServiceAccountApiKey(
        detail.value.item.id,
        selectedKey.value.id,
        {
          name: rotateForm.name,
          scopes: rotateForm.scopes,
          expires_at: rotateForm.expires_at ? new Date(rotateForm.expires_at).toISOString() : null,
        },
        auditReason.value,
      );
      plainKey.value = response.plain_key;
    } else {
      await consoleClient.forceExpireServiceAccountApiKey(detail.value.item.id, selectedKey.value.id, auditReason.value);
    }
    closeActionDrawer();
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join(", ") : "-";
}

function surfaceNames(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return t("noPublishedSurfaces");
  return value.map((surface) => String((surface as Record<string, unknown>).name || (surface as Record<string, unknown>).id || "-")).join(", ");
}

onMounted(load);
</script>

<style scoped>
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-layout,
.panel-grid {
  display: grid;
  gap: 14px;
}

.hero-panel,
.panel,
.drawer {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 460px);
  gap: 14px;
  padding: 18px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.summary-grid div,
.dependency-row {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 48%, transparent);
  padding: 10px;
}

.summary-grid span,
.muted,
.dependency-row small {
  color: var(--color-text-muted);
  font-size: 12px;
}

.summary-grid strong {
  display: block;
  margin-top: 4px;
}

.panel-header,
.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px;
}

.panel-title {
  margin: 0;
}

.panel-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel-form,
.dependency-list,
.drawer-form {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.field {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.form-actions,
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.secret-once {
  display: grid;
  gap: 8px;
  border: 1px solid color-mix(in srgb, var(--color-warning) 45%, var(--color-border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-warning) 11%, var(--color-surface));
  padding: 12px;
}

.secret-once code {
  overflow-wrap: anywhere;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 8px 10px;
}

.embedded {
  border: 0;
  border-radius: 0;
}

.scope-cell {
  min-width: 220px;
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
  border-left-width: 1px;
  border-left-style: solid;
}

@media (max-width: 1000px) {
  .hero-panel,
  .panel-grid {
    grid-template-columns: 1fr;
  }

  .drawer {
    width: 100%;
  }
}
</style>
