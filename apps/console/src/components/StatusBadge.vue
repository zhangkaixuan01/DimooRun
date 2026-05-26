<template>
  <span class="status-badge" :data-tone="tone">{{ label }}</span>
</template>

<script setup lang="ts">
import type { StatusTone } from "../api/types";

const props = defineProps<{
  status: string;
  label?: string;
}>();

const toneMap: Record<string, StatusTone> = {
  succeeded: "success",
  ready: "success",
  active: "success",
  approved: "success",
  degraded: "warning",
  retrying: "warning",
  pending: "warning",
  failed: "danger",
  timeout: "danger",
  denied: "danger",
  dead_letter: "danger",
  paused: "neutral",
  stopped: "neutral",
  archived: "neutral",
  running: "running",
  warming_up: "running",
  draining: "running",
  leased: "running",
};

const tone = toneMap[props.status] ?? "neutral";
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge[data-tone="success"] {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.status-badge[data-tone="warning"] {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.status-badge[data-tone="danger"] {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.status-badge[data-tone="neutral"] {
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.status-badge[data-tone="running"] {
  background: var(--color-running-soft);
  color: var(--color-running);
}
</style>
