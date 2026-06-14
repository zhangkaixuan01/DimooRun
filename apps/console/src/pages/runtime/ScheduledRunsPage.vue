<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime Operations</p>
        <h1 class="page-title">Scheduled Runs</h1>
        <p class="page-subtitle">
          Preview next-fire behavior, bind Deployments, and pause, resume, or manually trigger periodic runtime work.
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && schedules.length === 0" />

    <div v-if="mode !== 'offline'" class="grid cols-2 sections">
      <form class="panel" @submit.prevent="createSchedule">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Schedule preview</h2>
            <p class="panel-copy">Validate timezone, next-fire time, and missed-run policy before creating the schedule.</p>
          </div>
        </div>
        <div class="panel-body form-stack">
          <label>
            <span>Name</span>
            <input v-model="form.name" class="input" placeholder="nightly-eval" />
          </label>
          <div class="form-grid">
            <label>
              <span>Schedule type</span>
              <select v-model="form.scheduleType" class="input">
                <option value="interval">interval</option>
                <option value="cron">cron</option>
              </select>
            </label>
            <label>
              <span>Timezone</span>
              <input v-model="form.timezone" class="input" placeholder="UTC" />
            </label>
          </div>
          <div class="form-grid">
            <label v-if="form.scheduleType === 'interval'">
              <span>Interval minutes</span>
              <input v-model.number="form.intervalMinutes" class="input" min="1" step="1" type="number" />
            </label>
            <label v-else>
              <span>Cron expression</span>
              <input v-model="form.cronExpression" class="input" placeholder="*/15 * * * *" />
            </label>
            <label>
              <span>Deployment ID</span>
              <input v-model.number="form.deploymentId" class="input" min="1" step="1" type="number" />
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>Backfill policy</span>
              <select v-model="form.backfillPolicy" class="input">
                <option value="none">none</option>
                <option value="latest">latest</option>
                <option value="all">all</option>
              </select>
            </label>
            <label>
              <span>Missed-run policy</span>
              <select v-model="form.missedRunPolicy" class="input">
                <option value="skip">skip</option>
                <option value="run_once">run_once</option>
                <option value="catch_up">catch_up</option>
              </select>
            </label>
          </div>
          <label>
            <span>Input template JSON</span>
            <textarea v-model="form.inputTemplateJson" class="input code-field" rows="5" spellcheck="false" />
          </label>
          <label>
            <span>Audit reason</span>
            <input v-model="form.auditReason" class="input" placeholder="create nightly schedule" />
          </label>
          <div class="action-row">
            <button class="button" type="button" :disabled="loading" @click="previewSchedule">
              Preview schedule
            </button>
            <button class="button primary" type="submit" :disabled="loading">
              Create schedule
            </button>
          </div>
          <section v-if="preview" class="preview-card">
            <strong>Next-run timeline</strong>
            <p class="muted">next fire: {{ preview.nextFireTime }}</p>
            <p class="muted">timezone: {{ preview.timezone }}</p>
            <p class="muted">shape: {{ preview.scheduleType }}</p>
          </section>
          <p v-if="actionMessage" class="action-message">{{ actionMessage }}</p>
        </div>
      </form>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">Schedules</h2>
            <p class="panel-copy">Active and paused runtime schedules in the current scope.</p>
          </div>
        </div>
        <div class="panel-body schedule-list">
          <button
            v-for="item in schedules"
            :key="item.id"
            class="schedule-item"
            :class="{ selected: selectedSchedule?.id === item.id }"
            type="button"
            @click="selectSchedule(item.id)"
          >
            <div class="schedule-head">
              <strong>{{ item.name || `schedule-${item.id}` }}</strong>
              <StatusBadge :status="item.status === 'active' ? 'ready' : 'degraded'" :label="item.status" />
            </div>
            <p class="muted">Deployment #{{ item.deploymentId }} · {{ item.scheduleType }}</p>
            <p class="muted">next fire: {{ item.nextFireTime || "n/a" }}</p>
          </button>
        </div>
      </section>
    </div>

    <section v-if="selectedSchedule" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">Schedule detail</p>
          <h2 class="panel-title">{{ selectedSchedule.name || `Schedule #${selectedSchedule.id}` }}</h2>
          <p class="muted">{{ selectedSchedule.timezone }} · {{ selectedSchedule.missedRunPolicy || "skip" }}</p>
        </div>
      </div>
      <div class="panel-body detail-grid">
        <aside class="summary">
          <dl>
            <div>
              <dt>Next fire</dt>
              <dd>{{ selectedSchedule.nextFireTime || "n/a" }}</dd>
            </div>
            <div>
              <dt>Pause reason</dt>
              <dd>{{ selectedSchedule.pauseReason || "none" }}</dd>
            </div>
            <div>
              <dt>Last triggered</dt>
              <dd>{{ selectedSchedule.lastTriggeredAt || "never" }}</dd>
            </div>
            <div>
              <dt>Last run</dt>
              <dd>
                <ResourceLink v-if="selectedSchedule.lastRunId" :to="`/runs/${selectedSchedule.lastRunId}`">
                  Run #{{ selectedSchedule.lastRunId }}
                </ResourceLink>
                <span v-else>none</span>
              </dd>
            </div>
            <div>
              <dt>Trigger count</dt>
              <dd>{{ selectedSchedule.triggerCount }}</dd>
            </div>
          </dl>
        </aside>
        <div class="workspace">
          <section class="child-panel">
            <h3>Manual controls</h3>
            <div class="action-row">
              <button
                class="button"
                type="button"
                :disabled="loading || selectedSchedule.status === 'paused'"
                @click="pauseSelected"
              >
                Pause schedule
              </button>
              <button
                class="button"
                type="button"
                :disabled="loading || selectedSchedule.status !== 'paused'"
                @click="resumeSelected"
              >
                Resume schedule
              </button>
              <button class="button primary" type="button" :disabled="loading" @click="triggerSelected">
                Trigger schedule
              </button>
            </div>
            <p class="muted">backfill: {{ selectedSchedule.backfillPolicy || "none" }}</p>
            <p class="muted">missed-run: {{ selectedSchedule.missedRunPolicy || "skip" }}</p>
            <p class="muted">last trigger source: {{ selectedSchedule.lastTriggerSource || "none" }}</p>
            <p class="muted">last run status: {{ selectedSchedule.lastRunStatus || "n/a" }}</p>
            <p class="muted">last task status: {{ selectedSchedule.lastTaskStatus || "n/a" }}</p>
          </section>
          <section class="child-panel">
            <h3>Input template</h3>
            <pre class="json-block">{{ formatJson(selectedSchedule.inputTemplate) }}</pre>
          </section>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { SchedulePreview, ScheduledRun } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const schedules = ref<ScheduledRun[]>([]);
const selectedSchedule = ref<ScheduledRun | null>(null);
const preview = ref<SchedulePreview | null>(null);
const actionMessage = ref("");
const form = reactive({
  name: "nightly-eval",
  scheduleType: "interval",
  timezone: "UTC",
  intervalMinutes: 30,
  cronExpression: "*/15 * * * *",
  deploymentId: 10,
  backfillPolicy: "latest",
  missedRunPolicy: "run_once",
  inputTemplateJson: JSON.stringify({ message: "scheduled" }, null, 2),
  auditReason: "create nightly schedule",
});

function parseInputTemplate(): Record<string, unknown> {
  const parsed = JSON.parse(form.inputTemplateJson);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? parsed as Record<string, unknown>
    : {};
}

function buildPayload(includeAuditReason = true): Record<string, unknown> {
  return {
    name: form.name,
    timezone: form.timezone,
    deployment_id: form.deploymentId,
    input_template: parseInputTemplate(),
    backfill_policy: form.backfillPolicy,
    missed_run_policy: form.missedRunPolicy,
    ...(form.scheduleType === "interval"
      ? { interval_minutes: form.intervalMinutes }
      : { cron_expression: form.cronExpression }),
    ...(includeAuditReason ? { audit_reason: form.auditReason } : {}),
  };
}

async function loadSchedules(selectId?: number) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    schedules.value = (await consoleClient.listSchedules()).items;
    const nextId = selectId || selectedSchedule.value?.id || schedules.value[0]?.id;
    if (nextId) {
      await selectSchedule(nextId);
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function selectSchedule(scheduleId: number) {
  selectedSchedule.value = await consoleClient.getSchedule(scheduleId);
}

async function previewSchedule() {
  loading.value = true;
  error.value = null;
  actionMessage.value = "";
  try {
    preview.value = await consoleClient.previewSchedule(buildPayload(false));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createSchedule() {
  loading.value = true;
  error.value = null;
  actionMessage.value = "";
  try {
    const created = await consoleClient.createSchedule(buildPayload(true));
    preview.value = null;
    actionMessage.value = `Schedule #${created.id} created.`;
    await loadSchedules(created.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function pauseSelected() {
  if (!selectedSchedule.value) return;
  loading.value = true;
  error.value = null;
  try {
    selectedSchedule.value = await consoleClient.pauseSchedule(selectedSchedule.value.id, {
      audit_reason: "pause schedule from console",
      pause_reason: "maintenance",
    });
    actionMessage.value = "Schedule paused.";
    await loadSchedules(selectedSchedule.value.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function resumeSelected() {
  if (!selectedSchedule.value) return;
  loading.value = true;
  error.value = null;
  try {
    selectedSchedule.value = await consoleClient.resumeSchedule(selectedSchedule.value.id, {
      audit_reason: "resume schedule from console",
    });
    actionMessage.value = "Schedule resumed.";
    await loadSchedules(selectedSchedule.value.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function triggerSelected() {
  if (!selectedSchedule.value) return;
  loading.value = true;
  error.value = null;
  try {
    const result = await consoleClient.triggerSchedule(selectedSchedule.value.id, {
      audit_reason: "manual trigger from console",
    });
    selectedSchedule.value = result.item;
    actionMessage.value = `Triggered Run #${result.triggeredRun.runId}.`;
    await loadSchedules(selectedSchedule.value.id);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function formatJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

onMounted(loadSchedules);
</script>

<style scoped>
.sections,
.detail-panel {
  margin-top: 16px;
}

.form-stack,
.schedule-list,
.workspace,
.child-panel {
  display: grid;
  gap: 14px;
}

.form-grid,
.detail-grid {
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

.schedule-item,
.preview-card {
  display: grid;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 12px;
  text-align: left;
}

.schedule-item.selected {
  border-color: color-mix(in srgb, var(--color-accent) 55%, var(--color-border));
  background: var(--color-accent-soft);
}

.schedule-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary {
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
  .detail-grid {
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
