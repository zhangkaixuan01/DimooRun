<template>
  <AdminCollectionPage
    :title="t('apiKeys')"
    :kicker="t('machineIdentity')"
    :description="t('apiKeysCopy')"
    resource-path="/v1/api-keys"
    seed-name="api-key"
  />
</template>

<script setup lang="ts">
import AdminCollectionPage from "../admin/AdminCollectionPage.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>
