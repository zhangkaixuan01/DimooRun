<template>
  <AdminCollectionPage
    :title="t('publishedSurfaces')"
    :kicker="t('publishedKicker')"
    :description="t('publishedCopy')"
    resource-path="/v1/published-surfaces"
    seed-name="published-surface"
  />
</template>

<script setup lang="ts">
import AdminCollectionPage from "../admin/AdminCollectionPage.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>
