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
  border-radius: var(--radius-md);
  background: var(--color-surface-muted);
  padding: 14px;
}

.skeleton-block.table {
  gap: 12px;
  padding: 18px;
}

.skeleton-line {
  display: block;
  height: 12px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-surface) 72%, var(--color-border));
  background-size: 220% 100%;
}
</style>
