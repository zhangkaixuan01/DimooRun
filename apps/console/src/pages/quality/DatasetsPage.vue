<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("qualityLoop") }}</p>
        <h1 class="page-title">{{ t("datasetCaptureTitle") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="capture">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("details") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("datasetName") }}</span>
            <input v-model="form.datasetName" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("sourceRun") }}</span>
              <input v-model.number="form.sourceRunId" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("datasetLabel") }}</span>
              <input v-model="form.label" class="input" />
            </label>
          </div>
          <label>
            <span>{{ t("redactFields") }}</span>
            <input v-model="form.redactFields" class="input" />
          </label>
          <button class="button primary" type="submit" :disabled="busy || !canCapture">
            {{ t("captureRun") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("auditEvidence") }}</h2>
          <StatusBadge v-if="captureResult" :status="captureResult.duplicate ? 'pending' : 'ready'" :label="captureResult.duplicate ? 'reused' : 'captured'" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="captureResult">
            <p class="result-line">
              {{ captureResult.duplicate ? t("duplicateItemReused") : `${t("capturedDatasetItem")} #${captureResult.datasetItemId}` }}
            </p>
            <p>source_run_id: {{ captureResult.sourceRunId }}</p>
            <p>{{ previewLine("api_key") }}</p>
            <p>{{ value(captureResult.audit.action) }}</p>
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
import type { RunDatasetCapture } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const captureResult = ref<RunDatasetCapture | null>(null);
const form = reactive({
  datasetName: "support-regressions",
  sourceRunId: 1001,
  label: "provider-timeout",
  redactFields: "api_key",
});

const canCapture = computed(() => form.datasetName.trim() && Number(form.sourceRunId) > 0);

async function capture() {
  busy.value = true;
  error.value = null;
  try {
    captureResult.value = await consoleClient.captureRunDataset({
      dataset_name: form.datasetName,
      source_run_id: form.sourceRunId,
      label: form.label,
      redact_fields: redactFields(),
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function redactFields(): string[] {
  return form.redactFields.split(",").map((field) => field.trim()).filter(Boolean);
}

function previewLine(field: string): string {
  const input = captureResult.value?.payloadPreview.input;
  if (!input || typeof input !== "object" || Array.isArray(input)) return `${field}: -`;
  const valueAtField = (input as Record<string, unknown>)[field];
  return `${field}: ${value(valueAtField)}`;
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

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
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

.result-line {
  margin: 0;
  font-weight: 800;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
