<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("replayEvidence") }}</p>
        <h1 class="page-title">{{ t("replayComparison") }}</h1>
        <p class="page-subtitle">{{ t("replayComparisonCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="creating || !sourceRun || !candidateVersionId" @click="createComparison">
        {{ creating ? t("creating") : t("createComparison") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !sourceRun" />

    <section v-if="mode !== 'offline' && !loading && sourceRun" class="panel">
      <div class="panel-body compare-form">
        <label>
          <span>{{ t("candidateVersion") }}</span>
          <select v-model.number="candidateVersionId" class="select">
            <option v-for="version in versions" :key="version.id" :value="version.id">
              {{ version.version }} / {{ version.status }}
            </option>
          </select>
        </label>
        <label>
          <span>{{ t("replayConfig") }}</span>
          <textarea v-model="replayConfigJson" class="textarea" rows="4"></textarea>
        </label>
      </div>
    </section>

    <section v-if="comparison" class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">{{ t("comparison") }} #{{ comparison.comparisonId }}</h2>
          <p class="muted">{{ t("sourceImmutableCopy") }}</p>
        </div>
        <StatusBadge :status="comparison.regressionSignal === 'unchanged' ? 'succeeded' : 'failed'" :label="comparison.regressionSignal" />
      </div>
      <div class="panel-body comparison-grid">
        <div>
          <h3>{{ t("sourceRun") }} #{{ comparison.sourceRun.id }}</h3>
          <pre>{{ formatRun(comparison.sourceRun) }}</pre>
        </div>
        <div>
          <h3>{{ t("replayRun") }} #{{ comparison.replayRun.id }}</h3>
          <pre>{{ formatRun(comparison.replayRun) }}</pre>
        </div>
        <div>
          <h3>{{ t("diffStates") }}</h3>
          <dl class="diff-list">
            <div>
              <dt>{{ t("input") }}</dt>
              <dd>{{ comparison.inputDiff.changed ? t("inputChanged") : t("inputUnchanged") }}</dd>
            </div>
            <div>
              <dt>{{ t("error") }}</dt>
              <dd>{{ comparison.errorDiff.changed ? t("errorChanged") : t("errorUnchanged") }}</dd>
            </div>
            <div>
              <dt>{{ t("events") }}</dt>
              <dd>{{ comparison.eventDiff.sourceCount }} -> {{ comparison.eventDiff.replayCount }}</dd>
            </div>
            <div>
              <dt>{{ t("latencyDelta") }}</dt>
              <dd>{{ comparison.latencyDeltaMs ?? "-" }}</dd>
            </div>
          </dl>
          <p class="muted">{{ t("sourceRemainsImmutable") }}</p>
        </div>
      </div>
    </section>

    <section v-if="comparison" class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("datasetCapture") }}</h2></div>
      <div class="panel-body compare-form">
        <label>
          <span>{{ t("datasetName") }}</span>
          <input v-model="datasetName" class="input" />
        </label>
        <label>
          <span>{{ t("datasetLabel") }}</span>
          <input v-model="datasetLabel" class="input" />
        </label>
        <button class="button" type="button" :disabled="capturing || !datasetName.trim()" @click="captureEvidence">
          {{ capturing ? t("saving") : t("saveEvidence") }}
        </button>
        <p v-if="capture" class="muted">
          {{ t("savedEvidenceTo") }} {{ capture.datasetName }}<br />
          source_run_id: {{ capture.sourceRunId }}<br />
          replay_run_id: {{ capture.replayRunId }}
        </p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { AgentVersion, DatasetCapture, ReplayComparison, ResourceId, Run } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const route = useRoute();
const { t } = useI18n();
const mode = apiMode();
const sourceRunId = computed(() => Number(route.query.source_run_id || 0));
const loading = ref(false);
const creating = ref(false);
const capturing = ref(false);
const error = ref<ConsoleApiError | null>(null);
const sourceRun = ref<Run | null>(null);
const versions = ref<AgentVersion[]>([]);
const candidateVersionId = ref<ResourceId | null>(null);
const replayConfigJson = ref('{"temperature":0}');
const comparison = ref<ReplayComparison | null>(null);
const datasetName = ref("");
const datasetLabel = ref("");
const capture = ref<DatasetCapture | null>(null);

async function loadSource() {
  if (mode === "offline" || !sourceRunId.value) return;
  loading.value = true;
  error.value = null;
  try {
    sourceRun.value = await consoleClient.getRun(sourceRunId.value);
    versions.value = (await consoleClient.listAgentVersions(Number(sourceRun.value?.agent))).items;
    candidateVersionId.value = versions.value.find((version) => String(version.id) !== sourceRun.value?.version)?.id
      ?? versions.value[0]?.id
      ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function parseReplayConfig(): Record<string, unknown> {
  const parsed = JSON.parse(replayConfigJson.value || "{}");
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? parsed as Record<string, unknown>
    : {};
}

async function createComparison() {
  if (!sourceRun.value || !candidateVersionId.value) return;
  creating.value = true;
  error.value = null;
  capture.value = null;
  try {
    comparison.value = await consoleClient.createReplayComparison({
      source_run_id: sourceRun.value.id,
      candidate_agent_version_id: candidateVersionId.value,
      replay_config: parseReplayConfig(),
    }, { auditReason: "create replay comparison from console" });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

async function captureEvidence() {
  if (!comparison.value) return;
  capturing.value = true;
  error.value = null;
  try {
    capture.value = await consoleClient.captureReplayDataset(
      comparison.value.comparisonId,
      { dataset_name: datasetName.value.trim(), label: datasetLabel.value.trim() || undefined },
      { auditReason: "capture replay comparison evidence" },
    );
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    capturing.value = false;
  }
}

function formatRun(run: Run): string {
  return JSON.stringify({
    id: run.id,
    status: run.status,
    version: run.version,
    input: run.input ?? null,
    output: run.output ?? null,
    error: run.error ?? null,
  }, null, 2);
}

onMounted(loadSource);
</script>

<style scoped>
.compare-form {
  display: grid;
  grid-template-columns: minmax(220px, 0.5fr) minmax(320px, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.comparison-grid h3 {
  margin: 0 0 8px;
  font-size: 1rem;
}

.diff-list {
  display: grid;
  gap: 10px;
  margin: 0;
}

.diff-list div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
}

pre {
  overflow: auto;
  min-height: 220px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

@media (max-width: 1000px) {
  .compare-form,
  .comparison-grid {
    grid-template-columns: 1fr;
  }
}
</style>
