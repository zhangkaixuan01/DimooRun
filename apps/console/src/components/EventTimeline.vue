<template>
  <ol class="timeline">
    <li v-for="event in events" :key="event.eventId" class="timeline-item">
      <span class="dot" :data-status="event.status" />
      <button
        class="timeline-card"
        type="button"
        :data-selected="event.eventId === selectedEventId"
        @click="emit('select', event)"
      >
        <div class="timeline-top">
          <strong>{{ event.type }}</strong>
          <span class="mono">#{{ event.sequence }}</span>
        </div>
        <p>{{ event.summary }}</p>
        <time>{{ formatDateTime(event.timestamp) }}</time>
      </button>
    </li>
  </ol>
</template>

<script setup lang="ts">
import type { RuntimeEvent } from "../api/types";
import { formatDateTime } from "../utils/dateTime";

defineProps<{
  events: RuntimeEvent[];
  selectedEventId?: string | null;
}>();
const emit = defineEmits<{
  select: [event: RuntimeEvent];
}>();
</script>

<style scoped>
.timeline {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline-item {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 10px;
}

.dot {
  width: 10px;
  height: 10px;
  margin-top: 13px;
  border-radius: 999px;
  background: var(--color-running);
}

.dot[data-status="failed"] {
  background: var(--color-danger);
}

.dot[data-status="succeeded"] {
  background: var(--color-success);
}

.timeline-card {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 10px 12px;
  text-align: left;
}

.timeline-card:hover,
.timeline-card[data-selected="true"] {
  border-color: var(--color-accent);
  background: color-mix(in srgb, var(--color-accent-soft) 48%, var(--color-surface-raised));
}

.timeline-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 13px;
}

p {
  margin: 6px 0;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.45;
}

time {
  color: var(--color-text-soft);
  font-size: 12px;
}
</style>
