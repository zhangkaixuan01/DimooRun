<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Enterprise Ops</p>
        <h1 class="page-title">Webhook Subscriptions</h1>
      </div>
      <button class="button" type="button" :disabled="loading" @click="load">Refresh</button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && subscriptions.length === 0" />

    <section v-if="mode !== 'offline' && !loading && !error" class="panel">
      <DataTable :columns="columns" :rows="subscriptions" row-key="id" label="Webhook Subscriptions">
        <template #cell-target="{ row }"><span class="mono">{{ row.target_url || row.target_ref }}</span></template>
        <template #cell-events="{ row }">{{ eventTypes(row) }}</template>
        <template #cell-secret="{ row }">{{ row.secret_ref ? "[REDACTED]" : "-" }}</template>
        <template #cell-status="{ row }"><StatusBadge :status="String(row.status || 'active')" :label="String(row.status || 'active')" /></template>
        <template #cell-last="{ row }">{{ row.last_delivery_status || "none" }}</template>
        <template #cell-actions="{ row }">
          <button class="button" type="button" @click="validate(row)">Validate webhook</button>
        </template>
      </DataTable>
    </section>

    <section v-if="lastValidation" class="panel result-panel">
      <strong>last delivery</strong>
      <span>{{ validationStatus }}</span>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type AdminResource, type ConsoleApiError } from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import DataTable from "../../components/DataTable.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const subscriptions = ref<AdminResource[]>([]);
const lastValidation = ref<Record<string, unknown> | null>(null);
const columns = [
  { key: "target", label: "Target URL" },
  { key: "events", label: "Event types" },
  { key: "retry_policy", label: "Retry policy" },
  { key: "secret", label: "Secret reference" },
  { key: "status", label: "Status" },
  { key: "last", label: "Delivery status" },
  { key: "actions", label: "Actions" },
];

const validationStatus = computed(() => {
  const delivery = lastValidation.value?.last_delivery;
  if (!delivery || typeof delivery !== "object") return "last delivery: unknown";
  return String((delivery as Record<string, unknown>).status || "unknown");
});

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    subscriptions.value = (await consoleClient.listAdminCollection("/v1/webhooks/subscriptions")).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function eventTypes(row: AdminResource): string {
  const value = row.event_types;
  return Array.isArray(value) ? value.join(", ") : String(value || "-");
}

async function validate(row: AdminResource) {
  lastValidation.value = await consoleClient.validateWebhookSubscription(row.id, {
    target_url: row.target_url,
    audit_reason: "operator webhook validation",
  });
}

onMounted(load);
</script>
