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
  min-height: 106px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-accent-quiet) 72%, transparent), transparent 64%),
    var(--color-surface);
  padding: 15px 16px;
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
  font-size: 26px;
  font-weight: 780;
  line-height: 1.1;
  letter-spacing: 0;
}

.metric-delta {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  color: var(--color-text-muted);
  padding: 3px 7px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.metric-delta[data-tone="good"] {
  border-color: color-mix(in srgb, var(--color-success) 42%, var(--color-border));
  background: var(--color-success-soft);
  color: var(--color-success);
}

.metric-delta[data-tone="warn"] {
  border-color: color-mix(in srgb, var(--color-warning) 42%, var(--color-border));
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.metric-delta[data-tone="bad"] {
  border-color: color-mix(in srgb, var(--color-danger) 42%, var(--color-border));
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
</style>
