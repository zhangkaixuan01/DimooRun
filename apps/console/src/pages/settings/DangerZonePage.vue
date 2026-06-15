<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("platform") }}</p>
        <h1 class="page-title">{{ t("dangerZone") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="!loading" class="danger-grid">
      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("preflight") }}</p>
            <h2>{{ t("configurationAction") }}</h2>
          </div>
        </header>
        <div class="panel-body form-grid">
          <label>
            <span>{{ t("action") }}</span>
            <select v-model="selectedAction" class="select">
              <option value="rotate_object_store_credentials">rotate_object_store_credentials</option>
              <option value="freeze_environment_writes">freeze_environment_writes</option>
            </select>
          </label>
          <button class="button" type="button" @click="loadPreview">{{ t("runPreflight") }}</button>
          <div v-if="preview" class="preview-box">
            <StatusBadge :status="preview.available ? 'ready' : 'failed'" :label="preview.available ? t('statusReady') : t('statusBlocked')" />
            <div class="preview-meta">
              <strong>{{ preview.action }}</strong>
              <span>{{ preview.scope_kind }}</span>
              <span>{{ preview.risk_level }}</span>
            </div>
            <p>{{ preview.rollback_notes }}</p>
            <p class="confirmation-copy">{{ t("confirmationPhrase") }}: <strong>{{ preview.confirmation_phrase }}</strong></p>
            <div class="impact-box">
              <strong>{{ t("affectedResources") }}</strong>
              <ul class="compact-list">
                <li v-for="resource in preview.affected_resources" :key="resource.label">
                  {{ resource.label }}: {{ resource.count }}
                </li>
              </ul>
            </div>
            <ul class="compact-list">
              <li v-for="reason in preview.blocked_reasons" :key="reason">{{ reason }}</li>
              <li v-if="preview.blocked_reasons.length === 0">{{ t("noBlockingPreflightFindings") }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("apply") }}</p>
            <h2>{{ t("auditedDangerousChange") }}</h2>
          </div>
        </header>
        <form class="panel-body form-grid" @submit.prevent="applyAction">
          <label>
            <span>{{ t("confirmation") }}</span>
            <input v-model="confirmation" class="input" :placeholder="preview?.confirmation_phrase || ''" />
          </label>
          <label>
            <span>{{ t("rollbackNotes") }}</span>
            <textarea v-model="rollbackNotes" class="textarea" rows="3"></textarea>
          </label>
          <label>
            <span>{{ t("auditReason") }}</span>
            <input v-model="auditReason" class="input" />
          </label>
          <div v-if="result" class="result-box">
            <p class="success-copy">{{ result.status }}</p>
            <p>{{ t("requestId") }}: <strong>{{ result.request_id || "n/a" }}</strong></p>
            <p>{{ t("rollbackNotes") }}: <strong>{{ result.rollback_notes }}</strong></p>
            <p v-if="result.scope_setting">{{ t("environmentFreezeWrites") }}: <strong>{{ String(result.scope_setting.config.freeze_writes) }}</strong></p>
          </div>
          <button class="button danger" type="submit" :disabled="busy || !preview || !preview.available">
            {{ t("applyDangerousChange") }}
          </button>
        </form>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
  type DangerousActionPreview,
  type DangerousActionResult,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const selectedAction = ref("rotate_object_store_credentials");
const preview = ref<DangerousActionPreview | null>(null);
const result = ref<DangerousActionResult | null>(null);
const confirmation = ref("");
const rollbackNotes = ref("Document the rollback path before applying the change.");
const auditReason = ref("Controlled platform configuration change.");

async function loadPreview() {
  loading.value = true;
  error.value = null;
  result.value = null;
  try {
    preview.value = await consoleClient.preflightDangerousPlatformAction(selectedAction.value);
    confirmation.value = "";
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function applyAction() {
  if (!preview.value) return;
  busy.value = true;
  error.value = null;
  try {
    result.value = await consoleClient.runDangerousPlatformAction(
      selectedAction.value,
      {
        confirmation: confirmation.value,
        rollback_notes: rollbackNotes.value,
      },
      auditReason.value,
    );
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.danger-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid {
  display: grid;
  gap: 12px;
}

.form-grid label {
  display: grid;
  gap: 6px;
}

.form-grid span {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.preview-box {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

.preview-box p,
.success-copy {
  margin: 0;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.confirmation-copy {
  color: var(--color-text-muted);
}

.impact-box,
.result-box {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 82%, transparent);
  padding: 12px;
}

.compact-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
}

.success-copy {
  color: var(--color-success);
  font-weight: 700;
}

.result-box p {
  margin: 0;
}

@media (max-width: 900px) {
  .danger-grid {
    grid-template-columns: 1fr;
  }
}
</style>
