<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("gatewayGovernance") }}</p>
        <h1 class="page-title">{{ t("modelGatewayWorkbench") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="testGateway">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("modelGateway") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("gatewayName") }}</span>
            <input v-model="form.name" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("providerType") }}</span>
              <select v-model="form.providerType" class="select">
                <option value="openai">openai</option>
                <option value="anthropic">anthropic</option>
                <option value="azure-openai">azure-openai</option>
              </select>
            </label>
            <label>
              <span>{{ t("credentialReference") }}</span>
              <input v-model="form.credentialRef" class="input" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>{{ t("monthlyBudget") }}</span>
              <input v-model.number="form.monthlyBudgetUsd" class="input" min="0" type="number" />
            </label>
            <label>
              <span>{{ t("fallbackGateway") }}</span>
              <input v-model="form.fallbackGatewayRef" class="input" />
            </label>
          </div>
          <p v-for="fieldError in fieldErrors" :key="fieldError.field" class="field-error">
            {{ fieldError.message }}
          </p>
          <button class="button primary" type="submit" :disabled="busy || fieldErrors.length > 0">
            {{ t("testGateway") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("gatewayTestResult") }}</h2>
          <StatusBadge v-if="result" :status="credentialValid ? 'ready' : 'failed'" :label="value(result.safeHealthProbe.status)" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="result">
            <p class="result-line">{{ credentialValid ? t("credentialValid") : t("credentialInvalid") }}</p>
            <p v-if="disabledReason" class="notice danger">{{ disabledReason }}</p>
            <p>{{ t("health") }}: {{ value(result.safeHealthProbe.status) }}</p>
            <p>{{ t("budget") }}: ${{ money(result.budgetPreview.monthly_budget_usd) }}</p>
            <p>{{ t("fallback") }}: {{ value(result.fallbackPreview.target) }}</p>
            <p>{{ t("normalizedProviderError") }}: {{ value(result.providerErrorNormalization.normalized_code) }}</p>
            <p>{{ t("auditPreview") }}: {{ value(result.auditPreview.action) }}</p>
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
import type { ModelGatewayTestResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { validateModelGatewayForm } from "../../forms/validators";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const result = ref<ModelGatewayTestResult | null>(null);
const form = reactive({
  name: "primary-openai",
  providerType: "openai",
  credentialRef: "secret:model-openai",
  monthlyBudgetUsd: 500,
  fallbackGatewayRef: "gateway:backup-openai",
});

const fieldErrors = computed(() => validateModelGatewayForm({
  name: form.name,
  provider_type: form.providerType,
  credential_ref: form.credentialRef,
}));
const credentialValid = computed(() => result.value?.credentialValidation.valid === true);
const disabledReason = computed(() => value(result.value?.credentialValidation.disabled_action_reason));

async function testGateway() {
  busy.value = true;
  error.value = null;
  try {
    result.value = await consoleClient.testModelGateway({
      name: form.name,
      provider_type: form.providerType,
      credential_ref: form.credentialRef,
      monthly_budget_usd: form.monthlyBudgetUsd,
      fallback_gateway_ref: form.fallbackGatewayRef,
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

function money(input: unknown): string {
  const numberValue = Number(input || 0);
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(2);
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

.field-error,
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
