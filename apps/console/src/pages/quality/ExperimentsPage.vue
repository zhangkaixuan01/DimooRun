<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("qualityLoop") }}</p>
        <h1 class="page-title">{{ t("experimentWorkbench") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="run">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("details") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("experimentName") }}</span>
            <input v-model="form.name" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("dataset") }}</span>
              <input v-model.number="form.datasetId" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("candidateVersion") }}</span>
              <input v-model.number="form.candidateVersionId" class="input" min="1" type="number" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>{{ t("agent") }}</span>
              <input v-model.number="form.agentId" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("minimumScore") }}</span>
              <input v-model.number="form.minimumScore" class="input" min="0" step="0.1" type="number" />
            </label>
          </div>
          <button class="button primary" type="submit" :disabled="busy || !canRun">
            {{ t("runExperiment") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("qualityGate") }}</h2>
          <StatusBadge v-if="result" :status="gateStatus === 'passed' ? 'ready' : 'failed'" :label="gateStatus" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="result">
            <p class="result-line">{{ t("experimentRun") }} #{{ value(result.run.id) }}</p>
            <p>{{ t("averageScore") }}: {{ value(result.scoreDistribution.average_score) }}</p>
            <p>{{ t("qualityGate") }}: {{ gateStatus }}</p>
            <p>{{ t("promotion") }}: {{ result.qualityGate.promotion_allowed === true ? t("allowed") : t("blocked") }}</p>
            <p v-for="item in result.results" :key="String(item.id)">{{ value(item.evaluator_name) }}</p>
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
import type { ExperimentRunResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const result = ref<ExperimentRunResult | null>(null);
const form = reactive({
  name: "candidate-quality",
  agentId: 1,
  datasetId: 21,
  candidateVersionId: 12,
  minimumScore: 0.8,
});

const canRun = computed(() => form.name.trim() && form.agentId > 0 && form.datasetId > 0 && form.candidateVersionId > 0);
const gateStatus = computed(() => String(result.value?.qualityGate.status || ""));

async function run() {
  busy.value = true;
  error.value = null;
  try {
    result.value = await consoleClient.runExperiment({
      name: form.name,
      agent_id: form.agentId,
      dataset_id: form.datasetId,
      candidate_agent_version_id: form.candidateVersionId,
      evaluator_config: { min_score: form.minimumScore, evaluators: ["exact_match"] },
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
