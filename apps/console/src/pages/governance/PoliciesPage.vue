<template>
  <AdminCollectionPage
    :title="t('policies')"
    :kicker="t('policyEngine')"
    :description="t('policyEngine')"
    resource-path="/v1/policies"
    seed-name="policy"
  />
</template>

<script setup lang="ts">
import AdminCollectionPage from "../admin/AdminCollectionPage.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>
