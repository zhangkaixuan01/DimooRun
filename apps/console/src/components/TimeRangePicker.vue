<template>
  <select class="select" :aria-label="t('timeRange')">
    <option>{{ t("last15m") }}</option>
    <option selected>{{ t("last24h") }}</option>
    <option>{{ t("last7d") }}</option>
  </select>
</template>

<script setup lang="ts">
import { useI18n } from "../i18n/useI18n";

const { t } = useI18n();
</script>
