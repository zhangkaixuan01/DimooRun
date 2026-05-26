<template>
  <div class="cost">
    <div>
      <span>{{ t("promptTokens") }}</span>
      <strong>18.4k</strong>
    </div>
    <div>
      <span>{{ t("completionTokens") }}</span>
      <strong>7.1k</strong>
    </div>
    <div>
      <span>{{ t("modelCost") }}</span>
      <strong>$0.088</strong>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "../i18n/useI18n";

const { t } = useI18n();
</script>

<style scoped>
.cost {
  display: grid;
  gap: 10px;
}

.cost div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
}

.cost div:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

span {
  color: var(--color-text-muted);
}
</style>
