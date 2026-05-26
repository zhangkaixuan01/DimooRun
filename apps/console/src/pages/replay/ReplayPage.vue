<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("replay") }}</p>
        <h1 class="page-title">{{ t("replay") }}</h1>
        <p class="page-subtitle">{{ t("replayCopy") }}</p>
      </div>
      <button class="button primary" type="button">{{ t("createReplay") }}</button>
    </header>
    <div class="grid cols-3">
      <section class="panel step"><strong>1</strong><span>{{ t("selectFailedRun") }}</span><p>run_01HX9KB6W4</p></section>
      <section class="panel step"><strong>2</strong><span>{{ t("chooseCandidateVersion") }}</span><p>support-agent@0.3.3-rc1</p></section>
      <section class="panel step"><strong>3</strong><span>{{ t("compare") }}</span><p>{{ t("compareCopy") }}</p></section>
    </div>
    <section class="panel">
      <div class="panel-header"><h2 class="panel-title">{{ t("replayComparison") }}</h2></div>
      <div class="panel-body compare">
        <pre>source: POLICY_APPROVAL_REQUIRED
latency: 6420ms
cost: $0.088</pre>
        <pre>candidate: approval_request_created
latency: 3710ms
cost: $0.061</pre>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>

<style scoped>
.step {
  padding: 16px;
}

.step strong {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 999px;
  background: var(--color-accent);
  color: #fff;
}

.step span {
  display: block;
  margin-top: 12px;
  font-weight: 800;
}

.step p {
  color: var(--color-text-muted);
}

.compare {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

pre {
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}
</style>
