<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("gatewayGovernance") }}</p>
        <h1 class="page-title">{{ t("toolGatewayWorkbench") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="dryRun">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("tools") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <div class="form-grid">
            <label>
              <span>{{ t("toolName") }}</span>
              <input v-model="form.name" class="input" />
            </label>
            <label>
              <span>{{ t("riskLevel") }}</span>
              <select v-model="form.riskLevel" class="select">
                <option value="read">read</option>
                <option value="write">write</option>
                <option value="admin">admin</option>
                <option value="critical">critical</option>
              </select>
            </label>
          </div>
          <label>
            <span>{{ t("toolArguments") }}</span>
            <textarea v-model="form.argumentsJson" class="textarea" rows="6" />
          </label>
          <label>
            <span>{{ t("toolSchema") }}</span>
            <textarea v-model="form.schemaJson" class="textarea" rows="8" />
          </label>
          <p v-for="fieldError in validationErrors" :key="fieldError" class="field-error">
            {{ fieldError }}
          </p>
          <button class="button primary" type="submit" :disabled="busy || validationErrors.length > 0">
            {{ t("dryRunTool") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("toolDryRunResult") }}</h2>
          <StatusBadge v-if="result" :status="schemaValid ? 'ready' : 'failed'" :label="value(result.policyPreview.decision)" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="result">
            <p class="result-line">{{ schemaValid ? t("schemaValid") : t("schemaInvalid") }}</p>
            <p>{{ t("risk") }}: {{ value(result.riskClassification.level) }}</p>
            <p>{{ t("policy") }}: {{ value(result.policyPreview.decision) }}</p>
            <p>{{ t("approval") }}: {{ result.approvalRequirement.required === true ? t("required") : t("notRequired") }}</p>
            <a class="button link-button" :href="result.usageHistoryLink">{{ t("usageHistory") }}</a>
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
import type { ToolDryRunResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { validateToolSchema } from "../../forms/validators";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const result = ref<ToolDryRunResult | null>(null);
const form = reactive({
  name: "crm.update_ticket",
  riskLevel: "write",
  argumentsJson: '{"ticket_id":"T-100","status":"closed"}',
  schemaJson: '{\n  "type": "object",\n  "required": ["ticket_id", "status"],\n  "properties": {\n    "ticket_id": { "type": "string" },\n    "status": { "type": "string" }\n  }\n}',
});

const parsedSchema = computed(() => parseObject(form.schemaJson));
const parsedArguments = computed(() => parseObject(form.argumentsJson));
const validationErrors = computed(() => {
  const errors = validateToolSchema({
    name: form.name,
    risk_level: form.riskLevel,
    schema: parsedSchema.value.value,
  }).map((item) => item.message);
  if (parsedSchema.value.error) errors.push(parsedSchema.value.error);
  if (parsedArguments.value.error) errors.push(parsedArguments.value.error);
  return errors;
});
const schemaValid = computed(() => result.value?.schemaValidation.valid === true);

async function dryRun() {
  if (!parsedSchema.value.value || !parsedArguments.value.value) return;
  busy.value = true;
  error.value = null;
  try {
    result.value = await consoleClient.dryRunTool({
      name: form.name,
      risk_level: form.riskLevel,
      schema: parsedSchema.value.value,
      arguments: parsedArguments.value.value,
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function parseObject(input: string): { value: Record<string, unknown> | null; error: string | null } {
  try {
    const parsed = JSON.parse(input);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, error: t("jsonObjectRequired") };
    }
    return { value: parsed as Record<string, unknown>, error: null };
  } catch {
    return { value: null, error: t("invalidJson") };
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

.textarea {
  min-height: 120px;
  resize: vertical;
}

.field-error {
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 10px;
  font-weight: 800;
}

.result-line {
  margin: 0;
  font-weight: 800;
}

.link-button {
  width: max-content;
  text-decoration: none;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
