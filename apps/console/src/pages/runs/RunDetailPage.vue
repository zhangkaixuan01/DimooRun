<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("runDetail") }}</p>
        <h1 class="page-title">{{ currentRun?.id ?? runId }}</h1>
        <p class="page-subtitle">{{ t("runDetailCopy") }}</p>
      </div>
      <StatusBadge v-if="currentRun" :status="currentRun.status" :label="currentRun.status" />
    </header>

    <div class="run-grid">
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
import { computed } from "vue";

import { events, runs } from "../../api/mockData";
import EventTimeline from "../../components/EventTimeline.vue";
import RunCostBreakdown from "../../components/RunCostBreakdown.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{ runId: string }>();
const { t } = useI18n();
const currentRun = computed(() => runs.find((run) => run.id === props.runId) ?? runs[0]);
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

@media (max-width: 1100px) {
  .run-grid,
  .tabs {
    grid-template-columns: 1fr;
  }
}
</style>
