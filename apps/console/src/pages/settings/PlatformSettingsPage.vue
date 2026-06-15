<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("platform") }}</p>
        <h1 class="page-title">{{ t("platformSettings") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="snapshot && !loading && !error" class="settings-grid">
      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("runtime") }}</p>
            <h2>{{ t("currentMode") }}</h2>
          </div>
          <StatusBadge :status="snapshot.production_safety.status === 'safe' ? 'ready' : 'failed'" :label="snapshot.runtime_mode" />
        </header>
        <div class="panel-body key-grid">
          <div><span>{{ t("database") }}</span><strong>{{ snapshot.database_mode }}</strong></div>
          <div><span>{{ t("queue") }}</span><strong>{{ snapshot.queue_backend }}</strong></div>
          <div><span>{{ t("objectStore") }}</span><strong>{{ value(snapshot.object_store.backend) }}</strong></div>
          <div><span>{{ t("gateway") }}</span><strong>{{ value(snapshot.model_gateway_provider.default_gateway) }}</strong></div>
        </div>
        <p v-if="snapshot.runtime_write_protected" class="warning-copy">
          {{ t("productionReadOnlyCopy") }}
        </p>
      </section>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("safety") }}</p>
            <h2>{{ t("productionSafety") }}</h2>
          </div>
        </header>
        <div class="panel-body">
          <StatusBadge :status="snapshot.production_safety.status === 'safe' ? 'ready' : 'failed'" :label="snapshot.production_safety.status" />
          <ul class="warning-list">
            <li v-for="warning in snapshot.production_safety.warnings" :key="warning">{{ warning }}</li>
            <li v-if="snapshot.production_safety.warnings.length === 0">{{ t("noProductionSafetyWarnings") }}</li>
          </ul>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("defaults") }}</p>
            <h2>{{ t("environmentDefaults") }}</h2>
          </div>
        </header>
        <form class="panel-body form-grid" @submit.prevent="saveEnvironmentDefaults">
          <label>
            <span>{{ t("deploymentStrategy") }}</span>
            <select v-model="environmentStrategy" class="select">
              <option value="rolling">rolling</option>
              <option value="blue_green">blue_green</option>
              <option value="canary">canary</option>
            </select>
          </label>
          <label>
            <span>{{ t("routeVisibility") }}</span>
            <select v-model="routeVisibility" class="select">
              <option value="internal">internal</option>
              <option value="public">public</option>
            </select>
          </label>
          <label>
            <span>{{ t("auditReason") }}</span>
            <input v-model="auditReason" class="input" />
          </label>
          <p v-if="saveMessage" class="success-copy">{{ saveMessage }}</p>
          <button class="button primary" type="submit" :disabled="saving">{{ t("saveEnvironmentDefaults") }}</button>
        </form>
      </section>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("settingsScopes") }}</p>
            <h2>{{ t("configurationBoundaries") }}</h2>
          </div>
        </header>
        <div class="panel-body scope-grid">
          <article v-for="setting in snapshot.scope_defaults" :key="setting.scope_kind" class="scope-card">
            <div class="scope-card-header">
              <strong>{{ scopeTitle(setting.scope_kind) }}</strong>
              <span class="scope-mode">{{ setting.scope_kind === 'environment' ? t("editable") : t("readOnly") }}</span>
            </div>
            <dl class="scope-values">
              <div v-for="(entryValue, entryKey) in setting.config" :key="String(entryKey)">
                <dt>{{ formatKey(String(entryKey)) }}</dt>
                <dd>{{ value(entryValue) }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
  type PlatformSettingsSnapshot,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const saving = ref(false);
const error = ref<ConsoleApiError | null>(null);
const snapshot = ref<PlatformSettingsSnapshot | null>(null);
const environmentStrategy = ref("rolling");
const routeVisibility = ref("internal");
const auditReason = ref("Tune environment defaults for controlled rollout.");
const saveMessage = ref("");

function value(input: unknown) {
  return typeof input === "string" || typeof input === "number" ? String(input) : "n/a";
}

function scopeTitle(scopeKind: string) {
  switch (scopeKind) {
    case "organization":
      return t("organizationDefaults");
    case "project":
      return t("projectDefaults");
    case "environment":
      return t("environmentDefaults");
    default:
      return scopeKind;
  }
}

function formatKey(key: string) {
  return key.replaceAll("_", " ");
}

async function load() {
  loading.value = true;
  error.value = null;
  try {
    snapshot.value = await consoleClient.getPlatformSettingsSnapshot();
    const environmentDefaults = snapshot.value.scope_defaults.find((item) => item.scope_kind === "environment");
    environmentStrategy.value = String(environmentDefaults?.config.default_deployment_strategy || "rolling");
    routeVisibility.value = String(environmentDefaults?.config.default_route_visibility || "internal");
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function saveEnvironmentDefaults() {
  saving.value = true;
  error.value = null;
  saveMessage.value = "";
  try {
    await consoleClient.updateScopedPlatformSettings(
      "environment",
      {
        default_deployment_strategy: environmentStrategy.value,
        default_route_visibility: routeVisibility.value,
      },
      auditReason.value,
    );
    saveMessage.value = t("environmentDefaultsUpdated");
    await load();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.settings-grid {
  display: grid;
  gap: 18px;
}

.key-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.key-grid div,
.form-grid label {
  display: grid;
  gap: 6px;
}

.key-grid span,
.form-grid span {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.warning-copy {
  margin: 0 16px 16px;
  color: var(--color-warning);
  font-weight: 700;
}

.warning-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
}

.form-grid {
  display: grid;
  gap: 12px;
  max-width: 520px;
}

.scope-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.scope-card {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

.scope-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.scope-mode {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.scope-values {
  display: grid;
  gap: 8px;
  margin: 0;
}

.scope-values div {
  display: grid;
  gap: 4px;
}

.scope-values dt {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.scope-values dd {
  margin: 0;
  font-weight: 700;
}

.success-copy {
  margin: 0;
  color: var(--color-success);
  font-weight: 700;
}

@media (max-width: 900px) {
  .key-grid {
    grid-template-columns: 1fr;
  }

  .scope-grid {
    grid-template-columns: 1fr;
  }
}
</style>
