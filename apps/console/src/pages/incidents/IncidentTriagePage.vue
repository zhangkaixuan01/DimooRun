<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("enterpriseOps") }}</p>
        <h1 class="page-title">{{ t("incidentTriage") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="acknowledge">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("incidentResponse") }}</h2>
          <StatusBadge v-if="incidentResult" :status="String(incidentResult.incident.status || 'open')" />
        </div>
        <div class="panel-body form-stack">
          <div class="form-grid">
            <label>
              <span>{{ t("incident") }}</span>
              <input v-model.number="incidentForm.incidentId" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("notificationChannel") }}</span>
              <input v-model="incidentForm.notificationChannel" class="input" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>{{ t("linkedRun") }}</span>
              <input v-model.number="incidentForm.linkedRun" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("linkedTask") }}</span>
              <input v-model.number="incidentForm.linkedTask" class="input" min="1" type="number" />
            </label>
          </div>
          <label>
            <span>{{ t("linkedEvent") }}</span>
            <input v-model="incidentForm.linkedEvent" class="input" />
          </label>
          <label>
            <span>{{ t("auditNote") }}</span>
            <textarea v-model="incidentForm.auditNote" class="input" rows="3" />
          </label>
          <label>
            <span>{{ t("resolutionSummary") }}</span>
            <textarea v-model="incidentForm.resolutionSummary" class="input" rows="3" />
          </label>
          <div class="button-row">
            <button class="button primary" type="submit" :disabled="busy || !canAct">
              {{ t("acknowledgeIncident") }}
            </button>
            <button class="button" type="button" :disabled="busy || !canAct" @click="resolve">
              {{ t("resolveIncident") }}
            </button>
          </div>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("auditEvidence") }}</h2>
        </div>
        <div class="panel-body result-stack">
          <template v-if="incidentResult">
            <p class="result-line">
              {{ t("incident") }} #{{ value(incidentResult.incident.id) }} {{ value(incidentResult.incident.status) }}
            </p>
            <p v-for="line in evidenceLines" :key="line">{{ line }}</p>
            <p v-if="latestDelivery">delivery: {{ value(latestDelivery.status) }}</p>
            <p>{{ value(incidentResult.audit.action) }}</p>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>

      <form class="panel" @submit.prevent="sendNotification">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("notificationProbe") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <div class="form-grid">
            <label>
              <span>{{ t("channel") }}</span>
              <input v-model.number="notificationForm.channelId" class="input" min="1" type="number" />
            </label>
            <label>
              <span>{{ t("channelName") }}</span>
              <input v-model="notificationForm.channelName" class="input" />
            </label>
          </div>
          <label>
            <span>{{ t("targetRef") }}</span>
            <input v-model="notificationForm.targetRef" class="input" />
          </label>
          <label>
            <span>{{ t("probeMessage") }}</span>
            <input v-model="notificationForm.message" class="input" />
          </label>
          <button class="button primary" type="submit" :disabled="busy || !notificationForm.channelId">
            {{ t("sendTestNotification") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("deliveryAttempt") }}</h2>
          <StatusBadge v-if="notificationResult" :status="notificationResult.status" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="notificationResult">
            <p class="result-line">{{ t("notificationProbeSent") }}</p>
            <p>visible_to_operator: {{ value(notificationResult.deliveryAttempt.visible_to_operator) }}</p>
            <p>{{ value(notificationResult.audit.action) }}</p>
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
import type { IncidentWorkflowResult, NotificationTestResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const incidentResult = ref<IncidentWorkflowResult | null>(null);
const notificationResult = ref<NotificationTestResult | null>(null);
const incidentForm = reactive({
  incidentId: 201,
  linkedRun: 1001,
  linkedTask: 8001,
  linkedEvent: "evt-1001-attempt",
  notificationChannel: "pagerduty-primary",
  auditNote: "Escalated provider outage.",
  resolutionSummary: "Rerouted traffic to healthy gateway.",
});
const notificationForm = reactive({
  channelId: 55,
  channelName: "pagerduty-primary",
  targetRef: "pd://service/runtime",
  message: "Synthetic notification probe",
});

const canAct = computed(() => incidentForm.incidentId > 0 && incidentForm.auditNote.trim());
const latestDelivery = computed(() => incidentResult.value?.deliveryAttempts.at(-1) ?? null);
const evidenceLines = computed(() => {
  const evidence = incidentResult.value?.linkedEvidence ?? {};
  return [
    ...arrayValue(evidence.runs).map((item) => `run: ${item}`),
    ...arrayValue(evidence.tasks).map((item) => `task: ${item}`),
    ...arrayValue(evidence.events).map((item) => `event: ${item}`),
  ];
});

async function acknowledge() {
  await actOnIncident("acknowledge");
}

async function resolve() {
  await actOnIncident("resolve");
}

async function actOnIncident(action: "acknowledge" | "resolve") {
  busy.value = true;
  error.value = null;
  try {
    const payload = {
      audit_note: incidentForm.auditNote,
      resolution_summary: incidentForm.resolutionSummary,
      linked_runs: [incidentForm.linkedRun],
      linked_tasks: [incidentForm.linkedTask],
      linked_events: [incidentForm.linkedEvent],
      notify_channels: [incidentForm.notificationChannel],
    };
    incidentResult.value = action === "acknowledge"
      ? await consoleClient.acknowledgeIncident(incidentForm.incidentId, payload)
      : await consoleClient.resolveIncident(incidentForm.incidentId, payload);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function sendNotification() {
  busy.value = true;
  error.value = null;
  try {
    notificationResult.value = await consoleClient.testNotification({
      channel_id: notificationForm.channelId,
      channel_name: notificationForm.channelName,
      target_ref: notificationForm.targetRef,
      message: notificationForm.message,
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function arrayValue(input: unknown): string[] {
  return Array.isArray(input) ? input.map(String) : [];
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

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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
