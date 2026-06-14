<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("observability") }}</p>
        <h1 class="page-title">{{ t("budget") }}</h1>
        <p class="page-subtitle">Preview and persist spend guardrails before rollout, provider drift, or failed runs turn into silent budget regressions.</p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="mode !== 'offline'" class="grid cols-2 sections">
      <form class="panel" @submit.prevent="previewDraft">
        <div class="panel-header">
          <h2 class="panel-title">Budget policy draft</h2>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>{{ t("name") }}</span>
            <input v-model="form.name" class="input" placeholder="prod-spend-guardrail" />
          </label>
          <label>
            <span>{{ t("monthlyBudget") }}</span>
            <input v-model.number="form.thresholdUsd" class="input" min="0" step="0.01" type="number" />
          </label>
          <div class="form-grid">
            <label>
              <span>Scope type</span>
              <select v-model="form.scopeType" class="input">
                <option value="tenant">{{ t("tenant") }}</option>
                <option value="project">{{ t("project") }}</option>
                <option value="environment">{{ t("environment") }}</option>
                <option value="agent">{{ t("agent") }}</option>
                <option value="deployment">{{ t("deployment") }}</option>
              </select>
            </label>
            <label>
              <span>Scope ref</span>
              <input v-model="form.scopeRef" class="input" placeholder="10" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>Reset window</span>
              <select v-model="form.resetWindow" class="input">
                <option value="daily">daily</option>
                <option value="weekly">weekly</option>
                <option value="monthly">monthly</option>
              </select>
            </label>
            <label>
              <span>{{ t("notificationChannel") }}</span>
              <select v-model.number="form.channelId" class="input">
                <option v-for="channel in channels" :key="channel.id" :value="channel.id">
                  #{{ channel.id }} · {{ channel.targetRef }}
                </option>
              </select>
            </label>
          </div>
          <label>
            <span>Action mode</span>
            <select v-model="form.actionMode" class="input">
              <option value="warn">warn</option>
              <option value="reject">reject</option>
              <option value="require_approval">require_approval</option>
            </select>
          </label>
          <div class="drawer-actions">
            <button class="button" type="button" :disabled="loading" @click="savePolicy">
              Save policy
            </button>
            <button class="button primary" type="submit" :disabled="loading || !hasPreviewInput">
              {{ loading ? "Previewing" : "Preview budget policy" }}
            </button>
          </div>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Saved budget policies</h2>
            <p class="panel-copy">Persist reusable guardrails and replay their impact against the current environment.</p>
          </div>
        </div>
        <div class="panel-body">
          <div v-if="policies.length === 0" class="muted">No saved budget policies yet.</div>
          <div v-else class="policy-list">
            <button
              v-for="policy in policies"
              :key="policy.id"
              class="policy-item"
              :class="{ selected: policy.id === selectedPolicyId }"
              type="button"
              @click="selectPolicy(policy)"
            >
              <div class="policy-header">
                <strong>{{ policy.name }}</strong>
                <StatusBadge :status="policy.status" :label="policy.status" />
              </div>
              <p class="muted">
                {{ policy.scopeType }}<span v-if="policy.scopeRef"> / {{ policy.scopeRef }}</span>
                · {{ formatUsd(policy.thresholdUsd) }} / {{ policy.resetWindow }}
              </p>
              <div class="policy-actions">
                <button class="button" type="button" :disabled="loading" @click.stop="previewSaved(policy.id)">
                  Preview saved
                </button>
                <button class="button danger" type="button" :disabled="loading" @click.stop="deletePolicy(policy.id)">
                  {{ t("delete") }}
                </button>
              </div>
            </button>
          </div>
        </div>
      </section>
    </div>

    <section v-if="previewResult" class="panel contributors">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Projected impact</h2>
          <p class="panel-copy">{{ previewSource }}</p>
        </div>
        <StatusBadge
          :status="previewResult.wouldTrigger ? 'failed' : 'ready'"
          :label="previewResult.wouldTrigger ? 'triggered' : 'within budget'"
        />
      </div>
      <div class="panel-body impact-grid">
        <div class="impact-card">
          <span>Current spend</span>
          <strong>{{ formatUsd(previewResult.currentSpendUsd) }}</strong>
        </div>
        <div class="impact-card">
          <span>Projected spend</span>
          <strong>{{ formatUsd(previewResult.projectedSpendUsd) }}</strong>
        </div>
        <div class="impact-card">
          <span>Utilization</span>
          <strong>{{ formatPercent(previewResult.utilizationRatio) }}</strong>
        </div>
        <div class="impact-card">
          <span>Scope</span>
          <strong>{{ previewResult.scopeType }}<span v-if="previewResult.scopeRef"> / {{ previewResult.scopeRef }}</span></strong>
        </div>
      </div>
      <div class="panel-body detail-stack">
        <p>{{ previewResult.notificationPreview }}</p>
        <p>{{ previewResult.actionPreview }}</p>
      </div>
      <div class="panel-body table-wrap">
        <table>
          <thead>
            <tr>
              <th>Scope</th>
              <th>{{ t("cost") }}</th>
              <th>{{ t("runs") }}</th>
              <th>Latest run</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in previewResult.topContributors" :key="`${item.groupBy}:${item.key}`">
              <td>
                <strong>{{ item.label }}</strong>
                <div class="muted mono">{{ item.key }}</div>
              </td>
              <td>{{ formatUsd(item.totalCostUsd) }}</td>
              <td>{{ item.runCount }}</td>
              <td>
                <ResourceLink v-if="item.latestRunId" :to="`/runs/${item.latestRunId}`">
                  Run #{{ item.latestRunId }}
                </ResourceLink>
                <span v-else class="muted">{{ t("none") }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { BudgetPreview, CostBudgetPolicy, NotificationChannelOption } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const previewResult = ref<BudgetPreview | null>(null);
const previewSource = ref("Draft preview");
const policies = ref<CostBudgetPolicy[]>([]);
const channels = ref<NotificationChannelOption[]>([]);
const selectedPolicyId = ref<number | null>(null);
const form = reactive({
  name: "prod-spend-guardrail",
  thresholdUsd: 1.5,
  scopeType: "deployment",
  scopeRef: "10",
  resetWindow: "monthly",
  channelId: 0,
  actionMode: "require_approval",
});

const hasPreviewInput = computed(() => form.thresholdUsd > 0 && form.channelId > 0);

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [policyPage, channelPage] = await Promise.all([
      consoleClient.listCostBudgetPolicies(),
      consoleClient.listNotificationChannels(),
    ]);
    policies.value = policyPage.items;
    channels.value = channelPage.items.filter((item) => item.status !== "disabled");
    if (form.channelId === 0 && channels.value.length > 0) {
      form.channelId = channels.value[0].id;
    }
    if (selectedPolicyId.value !== null) {
      const existing = policies.value.find((item) => item.id === selectedPolicyId.value);
      if (!existing) selectedPolicyId.value = null;
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function previewDraft() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    previewResult.value = await consoleClient.previewBudgetPolicy({
      threshold_usd: form.thresholdUsd,
      scope_type: form.scopeType,
      scope_ref: form.scopeRef.trim() || null,
      reset_window: form.resetWindow,
      notification_channel: selectedChannelLabel(),
      action_mode: form.actionMode,
    });
    previewSource.value = "Draft preview";
  } catch (caught) {
    previewResult.value = null;
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function previewSaved(policyId: number) {
  loading.value = true;
  error.value = null;
  try {
    previewResult.value = await consoleClient.previewSavedBudgetPolicy(policyId);
    selectedPolicyId.value = policyId;
    const selected = policies.value.find((item) => item.id === policyId);
    previewSource.value = selected ? `Saved policy: ${selected.name}` : "Saved policy preview";
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function savePolicy() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const created = await consoleClient.createCostBudgetPolicy({
      name: form.name.trim() || "budget-policy",
      scope_type: form.scopeType,
      scope_ref: form.scopeRef.trim() || null,
      threshold_usd: form.thresholdUsd,
      reset_window: form.resetWindow,
      channel_id: form.channelId,
      action_mode: form.actionMode,
    });
    await load();
    await previewSaved(created.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function deletePolicy(policyId: number) {
  loading.value = true;
  error.value = null;
  try {
    await consoleClient.deleteCostBudgetPolicy(policyId);
    if (selectedPolicyId.value === policyId) {
      selectedPolicyId.value = null;
      previewResult.value = null;
      previewSource.value = "Draft preview";
    }
    await load();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function selectPolicy(policy: CostBudgetPolicy) {
  selectedPolicyId.value = policy.id;
  form.name = policy.name;
  form.thresholdUsd = policy.thresholdUsd;
  form.scopeType = policy.scopeType;
  form.scopeRef = policy.scopeRef || "";
  form.resetWindow = policy.resetWindow;
  form.channelId = policy.channelId;
  form.actionMode = policy.actionMode;
  void previewSaved(policy.id);
}

function selectedChannelLabel(): string {
  const channel = channels.value.find((item) => item.id === form.channelId);
  return channel?.targetRef || `channel:${form.channelId}`;
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

onMounted(load);
</script>

<style scoped>
.sections,
.contributors {
  margin-top: 16px;
}

.form-stack,
.detail-stack,
.policy-list {
  display: grid;
  gap: 14px;
}

.form-grid,
.impact-grid {
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
.muted,
.panel-copy {
  color: var(--color-text-muted);
}

.policy-item,
.impact-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 12px;
}

.policy-item {
  display: grid;
  gap: 8px;
  text-align: left;
}

.policy-item.selected {
  border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border));
  background: var(--color-accent-soft);
}

.policy-header,
.policy-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.policy-actions {
  justify-content: flex-start;
}

.impact-card span {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.impact-card strong {
  display: block;
  margin-top: 6px;
}

.table-wrap {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  border-bottom: 1px solid var(--color-border);
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}

@media (max-width: 900px) {
  .form-grid,
  .impact-grid {
    grid-template-columns: 1fr;
  }
}
</style>
