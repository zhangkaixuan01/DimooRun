<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("policyEngine") }}</p>
        <h1 class="page-title">{{ t("policies") }}</h1>
      </div>
      <button class="button primary" type="button">{{ t("createPolicy") }}</button>
    </header>
    <div class="grid cols-3">
      <section v-for="policy in policies" :key="policy.name" class="panel policy">
        <h2>{{ policy.name }}</h2>
        <p>{{ policy.scope }}</p>
        <StatusBadge :status="policy.status" :label="policy.status" />
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const policies = [
  { name: "destructive-tool-high-risk", scope: "tool.call / risk=high", status: "pending" },
  { name: "model-budget-prod", scope: "newapi-default / prod", status: "active" },
  { name: "deployment-operation-audit", scope: "deployment.pause|restart|stop", status: "active" },
];
</script>

<style scoped>
.policy {
  padding: 16px;
}

.policy h2 {
  margin: 0 0 8px;
  font-size: 16px;
}

.policy p {
  color: var(--color-text-muted);
}
</style>
