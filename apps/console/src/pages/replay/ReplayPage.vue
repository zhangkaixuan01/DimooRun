<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("replay") }}</p>
        <h1 class="page-title">{{ t("replay") }}</h1>
        <p class="page-subtitle">{{ t("replayCopy") }}</p>
      </div>
      <button
        class="button primary"
        type="button"
        :disabled="mode === 'offline' || creating || !selectedRunId || !selectedAgentVersionId"
        @click="createReplay"
      >
        {{ creating ? t("creating") : t("createReplay") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && runs.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && runs.length > 0" class="grid cols-3">
      <section class="panel step">
        <strong>1</strong>
        <span>{{ t("selectFailedRun") }}</span>
        <select v-model.number="selectedRunId" class="select">
          <option v-for="run in replayableRuns" :key="run.id" :value="run.id">
            #{{ run.id }} / {{ run.agent }} / {{ run.status }}
          </option>
        </select>
      </section>
      <section class="panel step">
        <strong>2</strong>
        <span>{{ t("chooseCandidateVersion") }}</span>
        <select v-model.number="selectedAgentVersionId" class="select">
          <option v-for="version in candidateVersions" :key="version.id" :value="version.id">
            {{ selectedRun ? `${selectedRun.agent}@${version.version}` : version.version }}
          </option>
        </select>
      </section>
      <section class="panel step">
        <strong>3</strong>
        <span>{{ t("compare") }}</span>
        <p v-if="replayResult">
          <ResourceLink :to="`/runs/${replayResult.id}`">#{{ replayResult.id }}</ResourceLink>
          <StatusBadge :status="replayResult.status" :label="replayResult.status" />
        </p>
        <p v-else>{{ t("compareCopy") }}</p>
      </section>
    </div>

    <section v-if="mode !== 'offline' && !loading && !error && selectedRun" class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("replayComparison") }}</h2></div>
      <div class="panel-body compare">
        <div>
          <p class="payload-label">{{ t("source") }}</p>
          <pre>{{ formatRun(selectedRun) }}</pre>
        </div>
        <div>
          <p class="payload-label">{{ t("replay") }}</p>
          <pre>{{ replayResult ? formatRun(replayResult) : t("emptyState") }}</pre>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { AgentVersion, ResourceId, Run } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const creating = ref(false);
const error = ref<ConsoleApiError | null>(null);
const runs = ref<Run[]>([]);
const candidateVersions = ref<AgentVersion[]>([]);
const selectedRunId = ref<ResourceId | null>(null);
const selectedAgentVersionId = ref<ResourceId | null>(null);
const replayResult = ref<Run | null>(null);
const replayableRuns = computed(() => {
  const failed = runs.value.filter((run) => run.status === "failed");
  return failed.length > 0 ? failed : runs.value;
});
const selectedRun = computed(() => runs.value.find((run) => run.id === selectedRunId.value) ?? null);
watch(selectedRun, async (run) => {
  replayResult.value = null;
  candidateVersions.value = [];
  selectedAgentVersionId.value = null;
  if (!run) return;
  try {
    candidateVersions.value = (await consoleClient.listAgentVersions(Number(run.agent))).items;
    selectedAgentVersionId.value = candidateVersions.value.find((version) => String(version.id) === run.version)?.id
      ?? candidateVersions.value[0]?.id
      ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
});

async function loadRuns() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    runs.value = (await consoleClient.listRuns()).items;
    selectedRunId.value = replayableRuns.value[0]?.id ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function replayRun(selectedRunId: ResourceId): Promise<Run> {
  return consoleClient.replayRun(selectedRunId, selectedAgentVersionId.value);
}

async function createReplay() {
  if (!selectedRunId.value) return;
  creating.value = true;
  error.value = null;
  try {
    replayResult.value = await replayRun(selectedRunId.value);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function formatRun(run: Run): string {
  return JSON.stringify(
    {
      id: run.id,
      status: run.status,
      input: run.input ?? null,
      output: run.output ?? null,
      error: run.error ?? null,
    },
    null,
    2,
  );
}

onMounted(loadRuns);
</script>

<style scoped>
.step {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 16px;
}

.step strong {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 999px;
  background: var(--color-accent);
  color: #fff;
}

.step span {
  font-weight: 800;
}

.step p {
  display: flex;
  min-height: 36px;
  align-items: center;
  gap: 10px;
  margin: 0;
  color: var(--color-text-muted);
}

.compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.payload-label {
  margin: 0 0 6px;
  font-weight: 700;
}

pre {
  overflow: auto;
  min-height: 180px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

@media (max-width: 900px) {
  .compare {
    grid-template-columns: 1fr;
  }
}
</style>
