<template>
  <section v-if="mode === 'offline'" class="state-panel">
    <strong>{{ t("apiNotConfigured") }}</strong>
    <span>{{ t("apiNotConfiguredCopy") }}</span>
  </section>
  <section v-else-if="error" class="state-panel error">
    <strong>{{ error.errorCode }}</strong>
    <span>{{ error.message }}</span>
    <small v-if="error.requestId" class="mono">request_id={{ error.requestId }}</small>
  </section>
  <section v-else-if="loading" class="state-panel">
    <strong>{{ t("loading") }}</strong>
    <span>{{ t("loadingCopy") }}</span>
  </section>
  <section v-else-if="empty" class="state-panel">
    <strong>{{ t("emptyState") }}</strong>
    <span>{{ t("emptyStateCopy") }}</span>
  </section>
</template>

<script setup lang="ts">
import type { ApiMode, ConsoleApiError } from "../api/client";
import { useI18n } from "../i18n/useI18n";

defineProps<{
  mode: ApiMode;
  loading?: boolean;
  empty?: boolean;
  error?: ConsoleApiError | null;
}>();

const { t } = useI18n();
</script>

<style scoped>
.state-panel {
  display: grid;
  gap: 7px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-accent-quiet) 72%, transparent), transparent 64%),
    var(--color-surface);
  box-shadow: var(--shadow-panel);
  padding: 18px 20px;
}

.state-panel.error {
  border-color: var(--color-danger);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-danger-soft) 44%, transparent), transparent),
    var(--color-surface);
}

.state-panel span,
.state-panel small {
  color: var(--color-text-muted);
}

.state-panel strong {
  font-size: 15px;
}
</style>
