<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("qualityLoop") }}</p>
        <h1 class="page-title">{{ t("qualityGate") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="preview">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("details") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("deployment") }}</span>
            <input v-model.number="form.deploymentId" class="input" min="1" type="number" />
          </label>
          <label>
            <span>{{ t("candidateVersion") }}</span>
            <input v-model.number="form.candidateVersionId" class="input" min="1" type="number" />
          </label>
          <label>
            <span>{{ t("experimentRun") }}</span>
            <input v-model.number="form.experimentRunId" class="input" min="1" type="number" />
          </label>
          <button class="button primary" type="submit" :disabled="busy || !canPreview">
            {{ t("previewGate") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("auditEvidence") }}</h2>
          <StatusBadge v-if="gate" :status="gate.status === 'passed' ? 'ready' : 'failed'" :label="gate.status" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="gate">
            <p class="result-line">{{ t("qualityGate") }}: {{ gate.status }}</p>
            <p>{{ t("promotion") }}: {{ gate.promotionAllowed ? t("allowed") : t("blocked") }}</p>
            <p v-if="gate.blockedReason">{{ gate.blockedReason }}</p>
            <p>{{ value(gate.audit.action) }}</p>
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
import type { QualityGatePreview } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const gate = ref<QualityGatePreview | null>(null);
const form = reactive({
  deploymentId: 10,
  candidateVersionId: 12,
  experimentRunId: 402,
});

const canPreview = computed(() => form.deploymentId > 0 && form.candidateVersionId > 0 && form.experimentRunId > 0);

async function preview() {
  busy.value = true;
  error.value = null;
  try {
    gate.value = await consoleClient.previewQualityGate({
      deployment_id: form.deploymentId,
      candidate_agent_version_id: form.candidateVersionId,
      experiment_run_id: form.experimentRunId,
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
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

.result-line {
  margin: 0;
  font-weight: 800;
}
</style>
