<template>
  <article class="metric-card">
    <div>
      <p class="metric-label">{{ label }}</p>
      <strong class="metric-value">{{ value }}</strong>
    </div>
    <span class="metric-delta" :data-tone="tone">{{ delta }}</span>
  </article>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  delta: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}>();
</script>

<style scoped>
.metric-card {
  display: flex;
  min-height: 102px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-surface-muted) 38%, transparent), transparent),
    var(--color-surface);
  padding: 16px;
  box-shadow: var(--shadow-panel);
}

.metric-label {
  margin: 0 0 10px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.metric-value {
  display: block;
  font-size: 24px;
  font-weight: 760;
  line-height: 1.1;
}

.metric-delta {
  border-radius: 999px;
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.metric-delta[data-tone="good"] {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.metric-delta[data-tone="warn"] {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.metric-delta[data-tone="bad"] {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
</style>
