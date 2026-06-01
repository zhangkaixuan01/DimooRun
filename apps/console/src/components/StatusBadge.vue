<template>
  <span class="status-badge" :data-tone="tone">{{ label }}</span>
</template>

<script setup lang="ts">
import { computed } from "vue";

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
  enabled: "success",
  degraded: "warning",
  retrying: "warning",
  pending: "warning",
  paused: "warning",
  failed: "danger",
  timeout: "danger",
  denied: "danger",
  dead_letter: "danger",
  rejected: "danger",
  disabled: "disabled",
  deleted: "disabled",
  stopped: "disabled",
  archived: "disabled",
  revoked: "disabled",
  expired: "disabled",
  cancelled: "disabled",
  running: "running",
  warming_up: "running",
  draining: "running",
  leased: "running",
};

const tone = computed(() => toneMap[props.status] ?? "neutral");
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 2px 7px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.status-badge::before {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
  content: "";
}

.status-badge[data-tone="success"] {
  border-color: color-mix(in srgb, var(--color-success) 36%, var(--color-border));
  background: var(--color-success-soft);
  color: var(--color-success);
}

.status-badge[data-tone="warning"] {
  border-color: color-mix(in srgb, var(--color-warning) 36%, var(--color-border));
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.status-badge[data-tone="danger"] {
  border-color: color-mix(in srgb, var(--color-danger) 36%, var(--color-border));
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.status-badge[data-tone="neutral"] {
  border-color: var(--color-border);
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.status-badge[data-tone="disabled"] {
  border-color: color-mix(in srgb, var(--color-text-soft) 36%, var(--color-border));
  background: color-mix(in srgb, var(--color-surface-muted) 66%, var(--color-surface));
  color: var(--color-text-soft);
  text-decoration: line-through;
  text-decoration-thickness: 1px;
  text-decoration-color: color-mix(in srgb, var(--color-text-soft) 62%, transparent);
}

.status-badge[data-tone="running"] {
  border-color: color-mix(in srgb, var(--color-running) 38%, var(--color-border));
  background: var(--color-running-soft);
  color: var(--color-running);
}
</style>
