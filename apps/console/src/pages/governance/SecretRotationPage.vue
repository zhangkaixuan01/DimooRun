<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("gatewayGovernance") }}</p>
        <h1 class="page-title">{{ t("secretRotation") }}</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="busy" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2">
      <form class="panel" @submit.prevent="validate">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("secrets") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <div class="form-grid">
            <label>
              <span>{{ t("secretName") }}</span>
              <input v-model="form.name" class="input" />
            </label>
            <label>
              <span>{{ t("secretProvider") }}</span>
              <input v-model="form.provider" class="input" />
            </label>
          </div>
          <label>
            <span>{{ t("secretReference") }}</span>
            <input v-model="form.ref" class="input" />
          </label>
          <label>
            <span>{{ t("usedBy") }}</span>
            <input v-model="form.usedBy" class="input" />
          </label>
          <label>
            <span>{{ t("rotationReason") }}</span>
            <input v-model="form.rotationReason" class="input" />
          </label>
          <p v-for="fieldError in fieldErrors" :key="fieldError.field" class="field-error">
            {{ fieldError.message }}
          </p>
          <div class="ops">
            <button class="button primary" type="submit" :disabled="busy || fieldErrors.length > 0">
              {{ t("validateSecret") }}
            </button>
            <button class="button" type="button" :disabled="busy || fieldErrors.length > 0" @click="rotate">
              {{ t("rotateSecret") }}
            </button>
          </div>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("details") }}</h2>
          <StatusBadge v-if="validation" :status="secretValid ? 'ready' : 'failed'" :label="value(validation.validation.provider)" />
        </div>
        <div class="panel-body result-stack">
          <template v-if="validation">
            <p class="result-line">{{ secretValid ? t("secretValid") : t("secretInvalid") }}</p>
            <p>{{ t("usedBy") }}: {{ value(validation.lastUsed.used_by) }}</p>
            <p>{{ t("auditPreview") }}: {{ value(validation.accessAudit.action) }}</p>
            <p>{{ t("valueHidden") }}</p>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>

          <div v-if="rotation" class="rotation-block">
            <h3>{{ t("secretRotationResult") }}</h3>
            <p>{{ t("rotated") }}: {{ value(rotation.rotation.status) }}</p>
            <p>{{ t("currentReference") }}: {{ value(rotation.rotation.current_ref) }}</p>
            <p>{{ t("previousReference") }}: {{ value(rotation.rotation.previous_ref) }}</p>
            <p>{{ t("auditPreview") }}: {{ value(rotation.accessAudit.action) }}</p>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { SecretRotationResult, SecretValidationResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { validateSecretRef } from "../../forms/validators";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const validation = ref<SecretValidationResult | null>(null);
const rotation = ref<SecretRotationResult | null>(null);
const form = reactive({
  name: "model-openai",
  provider: "vault",
  ref: "vault://project/model-openai",
  usedBy: "gateway:primary-openai",
  rotationReason: "scheduled rotation",
});

const fieldErrors = computed(() => validateSecretRef({
  name: form.name,
  provider: form.provider,
  ref: form.ref,
}));
const secretValid = computed(() => validation.value?.validation.valid === true);

async function validate() {
  busy.value = true;
  error.value = null;
  try {
    validation.value = await consoleClient.validateSecret(payload());
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function rotate() {
  busy.value = true;
  error.value = null;
  try {
    rotation.value = await consoleClient.rotateSecret(payload());
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function payload(): Record<string, unknown> {
  return {
    name: form.name,
    provider: form.provider,
    ref: form.ref,
    rotation_reason: form.rotationReason,
    access_context: { used_by: form.usedBy },
  };
}

function value(input: unknown): string {
  return input === null || input === undefined || input === "" ? "-" : String(input);
}
</script>

<style scoped>
.form-stack,
.result-stack,
.rotation-block {
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

.field-error {
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 10px;
  font-weight: 800;
}

.result-line,
.rotation-block h3,
.rotation-block p {
  margin: 0;
}

.result-line {
  font-weight: 800;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
