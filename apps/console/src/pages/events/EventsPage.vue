<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("eventStore") }}</p>
        <h1 class="page-title">{{ t("events") }}</h1>
        <p class="page-subtitle">{{ t("eventsCopy") }}</p>
      </div>
    </header>
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && events.length === 0" />
    <div v-if="mode !== 'offline' && !loading && !error && events.length > 0" class="events-grid">
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("eventTimeline") }}</h2></div>
        <div class="panel-body">
          <EventTimeline :events="events" :selected-event-id="selectedEventId" @select="selectEvent" />
        </div>
      </section>
      <section class="panel">
        <div class="panel-header"><h2 class="panel-title">{{ t("selectedEvent") }}</h2></div>
        <div class="panel-body event-detail">
          <template v-if="selectedEvent">
            <dl>
              <div>
                <dt>{{ t("run") }}</dt>
                <dd><ResourceLink :to="`/runs/${selectedEvent.runId}`">{{ selectedEvent.runId }}</ResourceLink></dd>
              </div>
              <div>
                <dt>{{ t("type") }}</dt>
                <dd>{{ selectedEvent.type }}</dd>
              </div>
              <div>
                <dt>{{ t("status") }}</dt>
                <dd><StatusBadge :status="selectedEvent.status" :label="selectedEvent.status" /></dd>
              </div>
              <div>
                <dt>{{ t("id") }}</dt>
                <dd class="mono">{{ selectedEvent.eventId }}</dd>
              </div>
            </dl>
            <label>
              <span>{{ t("eventPayload") }}</span>
              <pre>{{ formatJson(selectedEvent.payload ?? selectedEvent) }}</pre>
            </label>
          </template>
          <p v-else class="muted">{{ t("emptyState") }}</p>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import EventTimeline from "../../components/EventTimeline.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const events = ref<RuntimeEvent[]>([]);
const selectedEventId = ref<string | null>(null);
const selectedEvent = computed(() => events.value.find((event) => event.eventId === selectedEventId.value) ?? events.value[0] ?? null);

async function loadEvents() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    events.value = (await consoleClient.listEvents()).items;
    selectedEventId.value = events.value[0]?.eventId ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(loadEvents);

function selectEvent(event: RuntimeEvent) {
  selectedEventId.value = event.eventId;
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}
</script>

<style scoped>
.events-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(320px, 1.1fr);
  gap: 14px;
}

.event-detail {
  display: grid;
  align-content: start;
  gap: 14px;
}

.event-detail dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 0;
}

.event-detail dt,
label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.event-detail dd {
  margin: 4px 0 0;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

pre {
  overflow: auto;
  min-height: 220px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

@media (max-width: 980px) {
  .events-grid,
  .event-detail dl {
    grid-template-columns: 1fr;
  }
}
</style>
