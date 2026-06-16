<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Enterprise Ops</p>
        <h1 class="page-title">Alert Rules</h1>
      </div>
      <button class="button primary" type="button" @click="showCreate = true">New alert rule</button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && rules.length === 0" />

    <section v-if="mode !== 'offline' && !loading && !error" class="panel">
      <DataTable :columns="columns" :rows="rules" row-key="id" label="Alert Rules">
        <template #cell-name="{ row }"><strong>{{ row.name }}</strong></template>
        <template #cell-signal="{ row }"><span class="mono">{{ row.signal }}</span></template>
        <template #cell-status="{ row }"><StatusBadge :status="String(row.status || 'active')" :label="String(row.status || 'active')" /></template>
        <template #cell-last="{ row }">{{ row.last_triggered_at || "never" }}</template>
        <template #cell-actions="{ row }">
          <button class="button" type="button" @click="testRule(row)">Test notification</button>
        </template>
      </DataTable>
    </section>

    <section v-if="lastResult" class="panel result-panel">
      <strong>delivery attempt</strong>
      <span>{{ deliveryStatus }}</span>
    </section>

    <AppDrawer :open="showCreate" label="New alert rule" title="New alert rule" kicker="Enterprise Ops" @close="showCreate = false">
      <form class="drawer-form" @submit.prevent="saveRule">
        <label class="field">Name<input v-model="form.name" class="input" /></label>
        <label class="field">Signal<input v-model="form.signal" class="input" /></label>
        <label class="field">Threshold<input v-model.number="form.threshold" class="input" type="number" /></label>
        <label class="field">Channel<input v-model.number="form.channelId" class="input" type="number" /></label>
        <div class="drawer-actions">
          <button class="button primary" type="submit">Save alert rule</button>
        </div>
      </form>
    </AppDrawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import DataTable from "../../components/DataTable.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const showCreate = ref(false);
const rules = ref<AdminResource[]>([]);
const lastResult = ref<Record<string, unknown> | null>(null);
const form = reactive({ name: "", signal: "runtime.error_rate", threshold: 1, channelId: 901 });
const columns = [
  { key: "name", label: "Rule name" },
  { key: "signal", label: "Signal" },
  { key: "threshold", label: "Threshold" },
  { key: "channel_id", label: "Channel" },
  { key: "status", label: "Status" },
  { key: "last", label: "Last triggered" },
  { key: "actions", label: "Actions" },
];

const deliveryStatus = computed(() => {
  const attempt = lastResult.value?.delivery_attempt;
  if (!attempt || typeof attempt !== "object") return "-";
  return `status: ${String((attempt as Record<string, unknown>).status || "-")}`;
});

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    rules.value = (await consoleClient.listAdminCollection("/v1/alerts/rules")).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function saveRule() {
  const item = await consoleClient.createAdminItem("/v1/alerts/rules", {
    name: form.name,
    signal: form.signal,
    threshold: form.threshold,
    channel_id: form.channelId,
  });
  rules.value = [item, ...rules.value];
  showCreate.value = false;
}

async function testRule(row: AdminResource) {
  lastResult.value = await consoleClient.testAlertRule(row.id, {
    channel_id: row.channel_id,
    message: `Alert rule ${row.name} probe`,
    audit_reason: "operator test notification",
  });
}

onMounted(load);
</script>
