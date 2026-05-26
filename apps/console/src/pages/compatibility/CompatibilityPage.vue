<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("compatibilityKicker") }}</p>
        <h1 class="page-title">{{ t("compatibility") }}</h1>
        <p class="page-subtitle">{{ t("compatibilityCopy") }}</p>
      </div>
    </header>
    <div class="grid cols-3">
      <section class="panel mapping"><strong>{{ t("assistants") }}</strong><span>{{ t("assistantMapping") }}</span><code>/v1/assistants</code></section>
      <section class="panel mapping"><strong>{{ t("threads") }}</strong><span>{{ t("threadMapping") }}</span><code>/v1/threads</code></section>
      <section class="panel mapping"><strong>{{ t("runs") }}</strong><span>{{ t("runMapping") }}</span><code>/v1/threads/:id/runs</code></section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>

<style scoped>
.mapping {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.mapping strong {
  font-size: 18px;
}

.mapping span {
  color: var(--color-text-muted);
}

code {
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 8px;
}
</style>
