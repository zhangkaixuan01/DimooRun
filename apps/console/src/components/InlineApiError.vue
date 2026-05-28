<template>
  <section v-if="error" class="inline-error">
    <strong>{{ error.errorCode }}</strong>
    <span>{{ error.message }}</span>
    <small v-if="error.requestId" class="mono">request_id={{ error.requestId }}</small>
  </section>
</template>

<script setup lang="ts">
import type { ConsoleApiError } from "../api/client";

defineProps<{
  error: ConsoleApiError | null;
}>();
</script>

<style scoped>
.inline-error {
  display: grid;
  gap: 5px;
  border: 1px solid color-mix(in srgb, var(--color-danger) 68%, var(--color-border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-danger-soft) 56%, var(--color-surface));
  padding: 10px 12px;
}

.inline-error span,
.inline-error small {
  color: var(--color-text-muted);
}
</style>
