<template>
  <div class="skeleton-block" :class="variant" aria-hidden="true">
    <span
      v-for="index in lines"
      :key="index"
      class="skeleton-line"
      :style="{ width: widths[(index - 1) % widths.length] }"
    />
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  lines?: number;
  widths?: string[];
  variant?: "panel" | "table";
}>(), {
  lines: 4,
  widths: () => ["100%", "92%", "84%", "72%"],
  variant: "panel",
});
</script>

<style scoped>
.skeleton-block {
  display: grid;
  gap: 10px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-muted);
  padding: 16px;
}

.skeleton-block.table {
  gap: 12px;
  padding: 18px;
}

.skeleton-line {
  display: block;
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    color-mix(in oklab, var(--color-surface) 75%, transparent) 0%,
    color-mix(in oklab, var(--color-surface) 94%, white) 50%,
    color-mix(in oklab, var(--color-surface) 75%, transparent) 100%
  );
  background-size: 220% 100%;
  animation: shimmer 1.2s linear infinite;
}

@keyframes shimmer {
  from {
    background-position: 200% 0;
  }

  to {
    background-position: -20% 0;
  }
}
</style>
