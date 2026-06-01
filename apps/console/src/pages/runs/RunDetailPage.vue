<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runDetail") }}</p>
        <h1 class="page-title">{{ currentRun?.id ?? runId }}</h1>
        <p class="page-subtitle">{{ t("runDetailCopy") }}</p>
      </div>
      <div v-if="currentRun" class="run-actions">
        <StatusBadge :status="currentRun.status" :label="currentRun.status" />
        <button class="button danger" type="button" :disabled="pendingAction" @click="controlRun('cancel')">{{ t("cancel") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="controlRun('resume')">{{ t("resume") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="controlRun('retry')">{{ t("retry") }}</button>
        <button class="button" type="button" :disabled="pendingAction" @click="controlRun('replay')">{{ t("replay") }}</button>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !currentRun" />

    <div v-if="mode !== 'offline' && !loading && !error && currentRun" class="run-grid">
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("eventTimeline") }}</h2></div>
        <div class="panel-body"><EventTimeline :events="events" /></div>
      </section>

      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("selectedEvent") }}</h2></div>
        <div class="panel-body detail">
          <p><strong>policy.decision</strong></p>
          <p class="muted">{{ t("policyApprovalRequiredCopy") }}</p>
          <pre>{
  "error_code": "POLICY_APPROVAL_REQUIRED",
  "approval_policy": "destructive-tool-high-risk"
}</pre>
        </div>
      </section>

      <aside class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("metadataCost") }}</h2></div>
        <div class="panel-body">
          <p><strong>{{ t("deployment") }}</strong><br /><span class="mono">{{ currentRun?.deployment }}</span></p>
          <p><strong>{{ t("trace") }}</strong><br /><span class="mono">{{ currentRun?.traceId }}</span></p>
          <RunCostBreakdown />
        </div>
      </aside>
    </div>

    <section class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("input") }} / {{ t("output") }} / {{ t("artifacts") }} / {{ t("logs") }}</h2></div>
      <div class="panel-body tabs">
        <pre>{"ticket_id":"T-10291","message":"Customer asks for refund exception."}</pre>
        <pre>{"status":"blocked","reason":"approval_required"}</pre>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Run, RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import EventTimeline from "../../components/EventTimeline.vue";
import RunCostBreakdown from "../../components/RunCostBreakdown.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{ runId: string }>();
const runId = computed(() => Number(props.runId));
const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const events = ref<RuntimeEvent[]>([]);
const currentRun = ref<Run | null>(null);
const pendingAction = ref(false);

async function loadRun() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [run, eventPage] = await Promise.all([
      consoleClient.getRun(runId.value),
      consoleClient.listRunEvents(runId.value),
    ]);
    currentRun.value = run;
    events.value = eventPage.items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function controlRun(operation: string) {
  pendingAction.value = true;
  error.value = null;
  try {
    currentRun.value = await consoleClient.controlRun(runId.value, operation);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingAction.value = false;
  }
}

onMounted(loadRun);
</script>

<style scoped>
.run-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(320px, 1.2fr) minmax(240px, 0.7fr);
  gap: 14px;
}

pre {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.run-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 1100px) {
  .run-grid,
  .tabs {
    grid-template-columns: 1fr;
  }
}
</style>
