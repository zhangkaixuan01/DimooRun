<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("policyEngine") }}</p>
        <h1 class="page-title">{{ t("policyWorkbench") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="simulate">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("policyDraft") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("policyName") }}</span>
            <input v-model="form.name" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("resourceType") }}</span>
              <input v-model="form.resourceType" class="input" />
            </label>
            <label>
              <span>{{ t("action") }}</span>
              <input v-model="form.action" class="input" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>{{ t("decision") }}</span>
              <select v-model="form.decision" class="select">
                <option value="allow">allow</option>
                <option value="deny">deny</option>
                <option value="require_approval">require_approval</option>
              </select>
            </label>
            <label>
              <span>{{ t("priority") }}</span>
              <input v-model.number="form.priority" class="input" type="number" />
            </label>
          </div>
          <label>
            <span>{{ t("riskLevel") }}</span>
            <select v-model="form.riskLevel" class="select">
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </label>
          <label>
            <span>{{ t("reason") }}</span>
            <input v-model="form.reason" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("sampleResourceId") }}</span>
              <input v-model.number="form.sampleResourceId" class="input" type="number" />
            </label>
            <label>
              <span>{{ t("sampleEnvironment") }}</span>
              <input v-model="form.sampleEnvironment" class="input" />
            </label>
          </div>
          <label>
            <span>{{ t("auditReason") }}</span>
            <input v-model="form.auditReason" class="input" />
          </label>
          <div class="ops">
            <button class="button primary" type="submit" :disabled="busy">{{ t("simulatePolicy") }}</button>
            <button class="button" type="button" :disabled="busy" @click="activate">{{ t("activatePolicy") }}</button>
            <button class="button" type="button" :disabled="busy || !activation" @click="rollback">{{ t("rollbackPolicy") }}</button>
            <button class="button danger" type="button" :disabled="busy" @click="simulateDenied">{{ t("simulateDeniedSample") }}</button>
          </div>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("simulationResult") }}</h2>
          <StatusBadge v-if="simulation" :status="simulation.decision.result === 'deny' ? 'failed' : 'ready'" :label="simulation.decision.result" />
        </div>
        <div class="panel-body result-stack">
          <p v-if="deniedResource" class="notice danger">{{ t("policyDenied") }}: {{ deniedResource }}</p>
          <template v-if="simulation">
            <p class="result-line">{{ t("decision") }}: {{ simulation.decision.result }}</p>
            <p v-if="simulation.decision.reason" class="muted">{{ simulation.decision.reason }}</p>
            <div v-if="simulation.conflictWarnings.length > 0" class="result-list">
              <h3>{{ t("conflictWarnings") }}</h3>
              <p v-for="warning in simulation.conflictWarnings" :key="String(warning.code)">
                <strong>{{ warning.code }}</strong>
                <span>{{ warning.message }}</span>
              </p>
            </div>
            <div class="result-list">
              <h3>{{ t("auditPreview") }}</h3>
              <pre>{{ formatRecord(simulation.auditPreview) }}</pre>
            </div>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>

          <div v-if="activation" class="result-list">
            <h3>{{ t("activationResult") }}</h3>
            <p>{{ t("activatedVersion") }} {{ activation.version }}</p>
            <p>{{ t("rollbackTarget") }}: {{ t("version").toLowerCase() }} {{ activation.rollbackTarget.version }}</p>
          </div>
          <div v-if="activation" class="result-list">
            <h3>Audit comparison</h3>
            <p>
              Version
              {{ activation.comparison.fromVersion === null ? "draft" : activation.comparison.fromVersion }}
              ->
              {{ activation.comparison.toVersion }}
            </p>
            <p
              v-for="field in activation.comparison.changedFields"
              :key="field.field"
              class="comparison-line"
            >
              {{ field.field }}: {{ formatComparisonValue(field.before) }} -> {{ formatComparisonValue(field.after) }}
            </p>
          </div>
          <p v-if="rollbackMessage" class="notice">{{ rollbackMessage }}</p>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { PolicyActivation, PolicyDraft, PolicySimulation } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const simulation = ref<PolicySimulation | null>(null);
const activation = ref<PolicyActivation | null>(null);
const rollbackMessage = ref("");
const denied = ref(false);
const form = reactive({
  name: "deny-prod-delete",
  resourceType: "deployment",
  action: "delete",
  decision: "deny",
  priority: 10,
  riskLevel: "critical",
  reason: "Production deletion requires a separate approval path.",
  sampleResourceId: 42,
  sampleEnvironment: "prod",
  auditReason: "Block accidental production deletion.",
});

const deniedResource = computed(() => {
  if (!denied.value || !simulation.value?.matchedResources.length) return "";
  const resource = simulation.value.matchedResources[0];
  return `${resource.resourceType} #${resource.resourceId}`;
});

function draftPolicy(): PolicyDraft {
  return {
    name: form.name,
    type: "approval",
    resource_type: form.resourceType,
    action: form.action,
    decision: form.decision,
    priority: form.priority,
    risk_level: form.riskLevel,
    condition: { environment: form.sampleEnvironment },
    reason: form.reason,
  };
}

function sample(): Record<string, unknown> {
  return {
    resource_type: form.resourceType,
    resource_id: form.sampleResourceId,
    action: form.action,
    environment: form.sampleEnvironment,
  };
}

async function runWithState(action: () => Promise<void>) {
  busy.value = true;
  error.value = null;
  try {
    await action();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function simulate() {
  denied.value = false;
  await runWithState(async () => {
    simulation.value = await consoleClient.simulatePolicy(draftPolicy(), sample());
  });
}

async function activate() {
  await runWithState(async () => {
    activation.value = await consoleClient.activatePolicy(
      draftPolicy(),
      form.auditReason,
      activation.value?.version ?? null,
    );
  });
}

async function rollback() {
  const currentActivation = activation.value;
  if (!currentActivation) return;
  await runWithState(async () => {
    const result = await consoleClient.rollbackPolicy(
      currentActivation.rollbackTarget.policyId,
      currentActivation.rollbackTarget.version,
      form.auditReason,
      currentActivation.version,
    );
    activation.value = result;
    rollbackMessage.value = `${t("rolledBackToVersion")} ${result.rollbackTarget.version}`;
  });
}

async function simulateDenied() {
  denied.value = true;
  await runWithState(async () => {
    simulation.value = await consoleClient.simulatePolicy(draftPolicy(), sample());
  });
}

function formatRecord(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

function formatComparisonValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
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

.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-line {
  margin: 0;
  font-weight: 800;
}

.result-list {
  display: grid;
  gap: 8px;
}

.result-list h3,
.result-list p {
  margin: 0;
}

.result-list p {
  display: grid;
  gap: 3px;
}

.comparison-line {
  font-family: var(--font-mono, monospace);
}

.notice {
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 10px;
  font-weight: 800;
}

.notice.danger {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

pre {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 10px;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
