<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime Operations</p>
        <h1 class="page-title">Batch Runs</h1>
        <p class="page-subtitle">
          Expand bulk runtime work from dataset or inline input, inspect partial failures, and cancel queued items safely.
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && batches.length === 0" />

    <div v-if="mode !== 'offline'" class="grid cols-2 sections">
      <form class="panel" @submit.prevent="createBatch">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Batch create</h2>
            <p class="panel-copy">Choose inline inputs or dataset-backed expansion, then inspect queued and failed items immediately.</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>Name</span>
            <input v-model="form.name" class="input" placeholder="backfill-failed-runs" />
          </label>
          <div class="form-grid">
            <label>
              <span>Deployment ID</span>
              <input v-model.number="form.deploymentId" class="input" min="1" step="1" type="number" />
            </label>
            <label>
              <span>Concurrency</span>
              <input v-model.number="form.concurrency" class="input" min="1" step="1" type="number" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>Partial failure policy</span>
              <select v-model="form.partialFailurePolicy" class="input">
                <option value="continue">continue</option>
                <option value="abort">abort</option>
              </select>
            </label>
            <label>
              <span>Cancel policy</span>
              <select v-model="form.cancelPolicy" class="input">
                <option value="best_effort">best_effort</option>
                <option value="queued_only">queued_only</option>
              </select>
            </label>
          </div>
          <label>
            <span>Input items JSON</span>
            <textarea v-model="form.inputItemsJson" class="input code-field" rows="7" spellcheck="false" />
          </label>
          <label>
            <span>Audit reason</span>
            <input v-model="form.auditReason" class="input" placeholder="backfill failures" />
          </label>
          <div class="action-row">
            <button class="button primary" type="submit" :disabled="loading">
              Create batch
            </button>
          </div>
          <p v-if="actionMessage" class="action-message">{{ actionMessage }}</p>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Batch inventory</h2>
            <p class="panel-copy">Queued, partially failed, cancelled, and completed batch executions.</p>
          </div>
        </div>
        <div class="panel-body batch-list">
          <button
            v-for="item in batches"
            :key="item.id"
            class="batch-item"
            :class="{ selected: selectedBatch?.id === item.id }"
            type="button"
            @click="selectBatch(item.id)"
          >
            <div class="batch-head">
              <strong>{{ item.name || `batch-${item.id}` }}</strong>
              <StatusBadge :status="badgeStatus(item.status)" :label="item.status" />
            </div>
            <p class="muted">Deployment #{{ item.deploymentId }} · concurrency {{ item.concurrency }}</p>
            <p class="muted">
              queued {{ item.progressSummary.queuedItems }} · retrying {{ item.progressSummary.retryingItems }} · cancelled {{ item.progressSummary.cancelledItems }} · dead-letter {{ item.progressSummary.deadLetterItems }}
            </p>
          </button>
        </div>
      </section>
    </div>

    <section v-if="selectedBatch" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">Batch detail</p>
          <h2 class="panel-title">{{ selectedBatch.name || `Batch #${selectedBatch.id}` }}</h2>
          <p class="muted">partial failure: {{ selectedBatch.partialFailurePolicy || "continue" }}</p>
        </div>
      </div>
      <div class="panel-body detail-grid">
        <aside class="summary">
          <dl>
            <div>
              <dt>Total items</dt>
              <dd>{{ selectedBatch.progressSummary.totalItems }}</dd>
            </div>
            <div>
              <dt>Queued items</dt>
              <dd>{{ selectedBatch.progressSummary.queuedItems }}</dd>
            </div>
            <div>
              <dt>Failed items</dt>
              <dd>{{ selectedBatch.progressSummary.failedItems }}</dd>
            </div>
            <div>
              <dt>Dead-letter items</dt>
              <dd>{{ selectedBatch.progressSummary.deadLetterItems }}</dd>
            </div>
            <div>
              <dt>Cancelled items</dt>
              <dd>{{ selectedBatch.progressSummary.cancelledItems }}</dd>
            </div>
            <div>
              <dt>Completed items</dt>
              <dd>{{ selectedBatch.progressSummary.completedItems }}</dd>
            </div>
          </dl>
          <button class="button danger" type="button" :disabled="loading" @click="dialogOpen = true">
            Cancel batch
          </button>
        </aside>
        <div class="workspace">
          <section class="child-panel">
            <h3>Progress summary</h3>
            <div class="summary-cards">
              <div class="summary-card">
                <span>Queued</span>
                <strong>{{ selectedBatch.progressSummary.queuedItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Running</span>
                <strong>{{ selectedBatch.progressSummary.runningItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Retrying</span>
                <strong>{{ selectedBatch.progressSummary.retryingItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Failed</span>
                <strong>{{ selectedBatch.progressSummary.failedItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Dead-letter</span>
                <strong>{{ selectedBatch.progressSummary.deadLetterItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Cancelled</span>
                <strong>{{ selectedBatch.progressSummary.cancelledItems }}</strong>
              </div>
              <div class="summary-card">
                <span>Completed</span>
                <strong>{{ selectedBatch.progressSummary.completedItems }}</strong>
              </div>
            </div>
          </section>
          <section class="child-panel">
            <h3>Failed item drilldown</h3>
            <div class="item-list">
              <article
                v-for="item in selectedBatch.items"
                :key="`${selectedBatch.id}:${item.index}`"
                class="item-card"
                :class="{ failed: item.status === 'failed' }"
              >
                <div class="item-head">
                  <strong>item #{{ item.index }}</strong>
                  <StatusBadge :status="badgeStatus(item.status)" :label="item.status" />
                </div>
                <p v-if="item.errorCode" class="form-error">{{ item.errorCode }}</p>
                <p v-if="item.message" class="muted">{{ item.message }}</p>
                <p v-if="item.runId" class="muted">Run #{{ item.runId }} · Task #{{ item.taskId }}</p>
                <pre class="json-block">{{ formatJson(item.input) }}</pre>
              </article>
            </div>
          </section>
        </div>
      </div>
    </section>

    <DangerConfirmDialog
      :open="dialogOpen"
      title="Cancel batch"
      message="Cancel all queued items in the selected batch run."
      :items="selectedBatch ? [
        { label: 'Batch', value: String(selectedBatch.id) },
        { label: 'Queued items', value: String(selectedBatch.progressSummary.queuedItems) },
      ] : []"
      warning="Queued items will be marked cancelled and existing failures remain as evidence."
      :busy="loading"
      :error="error"
      confirm-label="确认"
      busy-label="处理中"
      @cancel="dialogOpen = false"
      @confirm="cancelSelectedBatch"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { BatchRun } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const batches = ref<BatchRun[]>([]);
const selectedBatch = ref<BatchRun | null>(null);
const actionMessage = ref("");
const dialogOpen = ref(false);
const form = reactive({
  name: "backfill-failed-runs",
  deploymentId: 10,
  concurrency: 2,
  partialFailurePolicy: "continue",
  cancelPolicy: "best_effort",
  inputItemsJson: JSON.stringify([{ message: "one" }, "bad-item", { message: "two" }], null, 2),
  auditReason: "backfill failures",
});

function parseItems(): unknown[] {
  const parsed = JSON.parse(form.inputItemsJson);
  return Array.isArray(parsed) ? parsed : [];
}

async function loadBatches(selectId?: number) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    batches.value = (await consoleClient.listBatchRuns()).items;
    const nextId = selectId || selectedBatch.value?.id || batches.value[0]?.id;
    if (nextId) {
      await selectBatch(nextId);
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function selectBatch(batchId: number) {
  selectedBatch.value = await consoleClient.getBatchRun(batchId);
}

async function createBatch() {
  loading.value = true;
  error.value = null;
  actionMessage.value = "";
  try {
    const created = await consoleClient.createBatchRun({
      name: form.name,
      deployment_id: form.deploymentId,
      input_items: parseItems(),
      concurrency: form.concurrency,
      retry_policy: { max_attempts: 2 },
      cancel_policy: form.cancelPolicy,
      partial_failure_policy: form.partialFailurePolicy,
      audit_reason: form.auditReason,
    });
    actionMessage.value = `Batch #${created.id} created.`;
    await loadBatches(created.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function cancelSelectedBatch() {
  if (!selectedBatch.value) return;
  loading.value = true;
  error.value = null;
  try {
    selectedBatch.value = await consoleClient.cancelBatchRun(selectedBatch.value.id, {
      audit_reason: "cancel batch from console",
    });
    actionMessage.value = "Batch cancelled.";
    dialogOpen.value = false;
    await loadBatches(selectedBatch.value.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function badgeStatus(status: string): string {
  if (status === "failed" || status === "partial_failed") return "degraded";
  if (status === "cancelled") return "disabled";
  if (status === "completed") return "ready";
  return "running";
}

function formatJson(value: Record<string, unknown> | null): string {
  return JSON.stringify(value || {}, null, 2);
}

onMounted(loadBatches);
</script>

<style scoped>
.sections,
.detail-panel {
  margin-top: 16px;
}

.form-stack,
.batch-list,
.workspace,
.child-panel,
.item-list {
  display: grid;
  gap: 14px;
}

.form-grid,
.detail-grid,
.summary-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-grid {
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

label span,
.muted,
.panel-copy,
.section-kicker {
  color: var(--color-text-muted);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.batch-item,
.item-card,
.summary-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 12px;
  text-align: left;
}

.batch-item.selected {
  border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border));
  background: var(--color-accent-soft);
}

.item-card.failed {
  border-color: color-mix(in srgb, var(--color-danger) 52%, var(--color-border));
}

.batch-head,
.item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary {
  display: grid;
  gap: 14px;
  border-right: 1px solid var(--color-border);
  padding-right: 16px;
}

.summary dl {
  display: grid;
  gap: 12px;
}

.summary dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
}

.summary dd {
  margin: 4px 0 0;
}

.json-block,
.code-field {
  font-family: var(--font-mono, "SFMono-Regular", Consolas, monospace);
}

.json-block {
  margin: 0;
  overflow: auto;
}

.action-message {
  color: var(--color-success);
  font-weight: 700;
}

@media (max-width: 900px) {
  .form-grid,
  .detail-grid,
  .summary-cards {
    grid-template-columns: 1fr;
  }

  .summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 16px;
  }
}
</style>
