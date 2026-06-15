<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("agentPackage") }}</p>
        <h1 class="page-title">{{ t("packageRegistration") }}</h1>
        <p class="page-subtitle">
          {{ t("packageRegistrationCopy") }}
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="validationMutation.busy.value" :error="error" />

    <div class="grid cols-2">
      <form class="panel package-form" @submit.prevent="validatePackage">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("validationRequest") }}</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("packageUriLabel") }}</span>
            <input v-model="form.packageUri" class="input" />
          </label>
          <div class="form-grid">
            <label>
              <span>{{ t("frameworkLabel") }}</span>
              <select v-model="form.framework" class="select">
                <option value="langgraph">langgraph</option>
                <option value="langchain-agent">langchain-agent</option>
                <option value="deepagents">deepagents</option>
              </select>
            </label>
            <label>
              <span>{{ t("adapterLabel") }}</span>
              <select v-model="form.adapter" class="select">
                <option value="langgraph">langgraph</option>
                <option value="langchain-agent">langchain-agent</option>
                <option value="deepagents">deepagents</option>
              </select>
            </label>
          </div>
          <label>
            <span>{{ t("entrypointLabel") }}</span>
            <input v-model="form.entrypoint" class="input" />
          </label>
          <label>
            <span>{{ t("requiredSecretRefs") }}</span>
            <input v-model="form.requiredSecretRefs" class="input" placeholder="vault://openai, vault://search" />
          </label>
          <JsonSchemaEditor
            v-model="form.manifestJson"
            :label="t('manifest')"
            :error="manifestError"
            :rows="12"
          />
          <p class="muted">{{ t("readyVersionsRequireValidationToken") }}</p>
          <button class="button primary" type="submit" :disabled="validationMutation.busy.value">
            {{ validationMutation.busy.value ? t("validating") : t("validatePackage") }}
          </button>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <h2 class="panel-title">{{ t("packageValidationResult") }}</h2>
          <StatusBadge v-if="result" :status="result.ready ? 'ready' : 'degraded'" :label="result.status" />
        </div>
        <div class="panel-body result-stack">
          <p v-if="!result" class="muted">{{ t("noValidationRunYet") }}</p>
          <template v-else>
            <dl>
              <div>
                <dt>{{ t("status") }}</dt>
                <dd>{{ result.status }}</dd>
              </div>
              <div>
                <dt>{{ t("validationToken") }}</dt>
                <dd class="mono">{{ result.validationToken || t("none") }}</dd>
              </div>
              <div>
                <dt>{{ t("nextAction") }}</dt>
                <dd>{{ result.nextAction }}</dd>
              </div>
            </dl>
            <div v-if="result.errors.length > 0" class="result-list">
              <h3>{{ t("validationErrors") }}</h3>
              <p v-for="item in result.errors" :key="item.code">
                <strong>{{ item.code }}</strong>
                <span>{{ item.message }}</span>
              </p>
            </div>
            <div v-if="result.warnings.length > 0" class="result-list warning-list">
              <h3>{{ t("dependencyWarnings") }}</h3>
              <p v-for="item in result.warnings" :key="item">{{ item }}</p>
            </div>
            <div v-if="result.missingSecretRefs.length > 0" class="result-list">
              <h3>{{ t("missingSecretRefs") }}</h3>
              <p v-for="item in result.missingSecretRefs" :key="item">{{ item }}</p>
            </div>
            <div class="result-list">
              <h3>{{ t("capabilities") }}</h3>
              <pre>{{ formatJson(result.capabilities) }}</pre>
            </div>
            <button
              v-if="result.ready && result.validationToken"
              class="button primary"
              type="button"
              @click="continueToReadyVersion"
            >
              {{ t("createReadyVersion") }}
            </button>
          </template>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import { createMutationAction } from "../../api/mutations";
import type { PackageValidationResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import JsonSchemaEditor from "../../components/JsonSchemaEditor.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { isJsonParseFailure, parseJsonObject, type JsonParseFailure } from "../../forms/jsonForm";
import { useI18n } from "../../i18n/useI18n";
import { clearReadyVersionDraft, writeReadyVersionDraft } from "../../workflows/packageValidationDraft";

const mode = apiMode();
const router = useRouter();
const { t } = useI18n();
const error = ref<ConsoleApiError | null>(null);
const manifestError = ref<JsonParseFailure | null>(null);
const result = ref<PackageValidationResult | null>(null);
const form = reactive({
  packageUri: "oci://registry.local/support-agent:1.0.0",
  framework: "langgraph",
  adapter: "langgraph",
  entrypoint: "agent:create_agent",
  requiredSecretRefs: "",
  manifestJson: JSON.stringify({
    name: "support-agent",
    runtime: {
      framework: "langgraph",
      adapter: "langgraph",
      entrypoint: "agent:create_agent",
    },
    capabilities: { invoke: true },
  }, null, 2),
});

const validationMutation = createMutationAction(async () => {
  const manifest = parseJsonObject(form.manifestJson);
  if (isJsonParseFailure(manifest)) {
    manifestError.value = manifest;
    throw new Error(manifest.message);
  }
  manifestError.value = null;
  return consoleClient.validatePackage({
    package_uri: form.packageUri,
    framework: form.framework,
    adapter: form.adapter,
    entrypoint: form.entrypoint,
    manifest,
    required_secret_refs: form.requiredSecretRefs
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  });
});

async function validatePackage() {
  error.value = null;
  try {
    result.value = await validationMutation.run(undefined, { auditReason: "validate package from console" });
    if (!result.value.ready || !result.value.validationToken) {
      clearReadyVersionDraft();
    }
  } catch (caught) {
    clearReadyVersionDraft();
    error.value = toConsoleApiError(caught);
  }
}

function formatJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

async function continueToReadyVersion() {
  if (!result.value?.ready || !result.value.validationToken) return;
  const manifest = parseJsonObject(form.manifestJson);
  if (isJsonParseFailure(manifest)) {
    manifestError.value = manifest;
    return;
  }
  manifestError.value = null;
  writeReadyVersionDraft({
    packageUri: form.packageUri.trim(),
    framework: form.framework.trim(),
    adapter: form.adapter.trim(),
    entrypoint: form.entrypoint.trim(),
    manifest,
    capabilities: result.value.capabilities,
    validationToken: result.value.validationToken,
    nextAction: result.value.nextAction,
    warnings: [...result.value.warnings],
  });
  await router.push({ path: "/agents", query: { workflow: "package-validation" } });
}
</script>

<style scoped>
.package-form {
  align-self: start;
}

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

label span,
dt {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

dl {
  display: grid;
  gap: 10px;
  margin: 0;
}

dd {
  margin: 0;
}

.result-list {
  display: grid;
  gap: 8px;
}

.result-list h3 {
  margin: 0;
  font-size: 15px;
}

.result-list p {
  display: grid;
  gap: 3px;
  margin: 0;
}

.warning-list {
  border-left: 3px solid var(--color-warning);
  padding-left: 10px;
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
