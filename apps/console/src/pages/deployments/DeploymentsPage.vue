<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("desiredWorkerHeartbeat") }}</p>
        <h1 class="page-title">{{ t("deployments") }}</h1>
        <p class="page-subtitle">{{ t("deploymentControlCopy") }}</p>
      </div>
    </header>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("deployment") }}</th>
            <th>{{ t("agent") }}</th>
            <th>{{ t("environment") }}</th>
            <th>{{ t("desiredStatus") }}</th>
            <th>{{ t("runtimeStatus") }}</th>
            <th>{{ t("instances") }}</th>
            <th>{{ t("backlog") }}</th>
            <th>{{ t("modelGateway") }}</th>
            <th>{{ t("operations") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="deployment in deployments" :key="deployment.id">
            <td class="mono">{{ deployment.id }}</td>
            <td>{{ deployment.agent }}@{{ deployment.version }}</td>
            <td>{{ deployment.environment }}</td>
            <td><StatusBadge :status="deployment.desiredStatus" :label="deployment.desiredStatus" /></td>
            <td><StatusBadge :status="deployment.runtimeStatus" :label="deployment.runtimeStatus" /></td>
            <td>{{ deployment.instances }}</td>
            <td>{{ deployment.queueBacklog }}</td>
            <td>{{ deployment.modelGateway }}</td>
            <td class="ops">
              <button class="button" type="button" @click="openDialog('pause', deployment)">{{ t("pause") }}</button>
              <button class="button" type="button" @click="openDialog('resume', deployment)">{{ t("resume") }}</button>
              <button class="button danger" type="button" @click="openDialog('restart', deployment)">{{ t("restart") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmImpactDialog
      v-if="selected"
      :open="dialogOpen"
      :title="`${operation} ${selected.id}`"
      :impact-target="selected.id"
      :environment="selected.environment"
      :affects-new-runs="operation !== 'restart'"
      :affects-existing-runs="operation === 'restart'"
      :writes-audit-log="true"
      :rollbackable="operation !== 'restart'"
      @cancel="dialogOpen = false"
      @confirm="confirmOperation"
    />
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";

import { deployments } from "../../api/mockData";
import type { Deployment } from "../../api/types";
import ConfirmImpactDialog from "../../components/ConfirmImpactDialog.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const dialogOpen = ref(false);
const selected = ref<Deployment | null>(null);
const operation = ref("pause");

function openDialog(nextOperation: string, deployment: Deployment) {
  operation.value = nextOperation;
  selected.value = deployment;
  dialogOpen.value = true;
}

function confirmOperation() {
  dialogOpen.value = false;
}
</script>

<style scoped>
.ops {
  display: flex;
  gap: 8px;
}
</style>
