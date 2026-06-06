<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("enterpriseOps") }}</p>
        <h1 class="page-title">{{ t("backupAndRestore") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="previewBackup">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("backupDryRun") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("backupPlan") }}</span>
            <input v-model.number="backupForm.planId" class="input" min="1" type="number" />
          </label>
          <label>
            <span>{{ t("backupTargets") }}</span>
            <input v-model="backupForm.targets" class="input" />
          </label>
          <label>
            <span>{{ t("storageRef") }}</span>
            <input v-model="backupForm.storageRef" class="input" />
          </label>
          <button class="button primary" type="submit" :disabled="busy || !backupForm.storageRef.trim()">
            {{ t("previewBackup") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("scopeProof") }}</h2>
          <StatusBadge v-if="backupResult" :status="backupResult.status === 'ready' ? 'ready' : 'failed'" :label="backupResult.status" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="backupResult">
            <p class="result-line">{{ t("backupDryRunReady") }}</p>
            <p>tenant_id: {{ value(backupResult.scopeProof.tenant_id) }}</p>
            <p>project_id: {{ value(backupResult.scopeProof.project_id) }}</p>
            <p>{{ value(backupResult.audit.action) }}</p>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>

      <form class="panel" @submit.prevent="previewRestore">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("restoreDryRun") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("backupRef") }}</span>
            <input v-model="restoreForm.backupRef" class="input" />
          </label>
          <label>
            <span>{{ t("restoreTargets") }}</span>
            <input v-model="restoreForm.targets" class="input" />
          </label>
          <label class="check-row">
            <input v-model="restoreForm.destructive" type="checkbox" />
            <span>{{ t("destructiveRestore") }}</span>
          </label>
          <label>
            <span>{{ t("confirmation") }}</span>
            <input v-model="restoreForm.confirmation" class="input" />
          </label>
          <button class="button primary" type="submit" :disabled="busy || !restoreForm.backupRef.trim()">
            {{ t("previewRestore") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("validationResult") }}</h2>
          <StatusBadge v-if="restoreResult" :status="restoreResult.status === 'ready' ? 'ready' : 'failed'" :label="restoreResult.status" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="restoreResult">
            <p class="result-line">{{ t("restoreDryRunReady") }}</p>
            <p>{{ value(restoreResult.audit.action) }}</p>
          </template>
          <template v-else-if="restoreError">
            <p class="result-line">{{ restoreError.errorCode }}</p>
            <p v-if="restoreGuardrailPhrase">{{ restoreGuardrailPhrase }}</p>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { BackupDryRunResult, RestoreDryRunResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const restoreError = ref<ConsoleApiError | null>(null);
const backupResult = ref<BackupDryRunResult | null>(null);
const restoreResult = ref<RestoreDryRunResult | null>(null);
const backupForm = reactive({
  planId: 9,
  targets: "runs,datasets,audit_logs",
  storageRef: "s3://dimoorun-backups/local",
});
const restoreForm = reactive({
  backupRef: "backup://2026-06-05/project",
  targets: "runs",
  destructive: true,
  confirmation: "",
});

const restoreGuardrailPhrase = computed(() => {
  const validation = restoreError.value?.details?.validation;
  if (!validation || typeof validation !== "object" || Array.isArray(validation)) return "";
  const phrase = (validation as Record<string, unknown>).destructive_confirmation_required;
  return typeof phrase === "string" ? phrase : "";
});

async function previewBackup() {
  busy.value = true;
  error.value = null;
  try {
    backupResult.value = await consoleClient.previewBackup({
      plan_id: backupForm.planId,
      scope: "project",
      targets: csv(backupForm.targets),
      storage_ref: backupForm.storageRef,
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function previewRestore() {
  busy.value = true;
  error.value = null;
  restoreError.value = null;
  try {
    restoreResult.value = await consoleClient.previewRestore({
      backup_ref: restoreForm.backupRef,
      restore_scope: "project",
      targets: csv(restoreForm.targets),
      destructive: restoreForm.destructive,
      confirmation: restoreForm.confirmation,
    });
  } catch (caught) {
    restoreResult.value = null;
    restoreError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function csv(input: string): string[] {
  return input.split(",").map((item) => item.trim()).filter(Boolean);
}

function value(input: unknown): string {
  return input === null || input === undefined || input === "" ? "-" : String(input);
}
</script>

<style scoped>
.form-stack,
.result-stack {
  display: grid;
  gap: 14px;
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

.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-row input {
  width: 16px;
  height: 16px;
}

.result-line {
  margin: 0;
  font-weight: 800;
}
</style>
