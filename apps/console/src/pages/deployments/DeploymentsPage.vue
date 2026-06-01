<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("desiredWorkerHeartbeat") }}</p>
        <h1 class="page-title">{{ t("deployments") }}</h1>
        <p class="page-subtitle">{{ t("deploymentControlCopy") }}</p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && deployments.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && deployments.length > 0" class="table-wrap">
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
              <button class="button" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('activate', deployment)">{{ t("activate") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('pause', deployment)">{{ t("pause") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('resume', deployment)">{{ t("resume") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('drain', deployment)">{{ t("drain") }}</button>
              <button class="button danger" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('stop', deployment)">{{ t("stop") }}</button>
              <button class="button danger" type="button" :disabled="pendingOperation === deployment.id" @click="openDialog('restart', deployment)">{{ t("restart") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConfirmImpactDialog
      v-if="selected"
      :open="dialogOpen"
      :title="`${operation} ${selected.id}`"
      :impact-target="String(selected.id)"
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
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Deployment } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ConfirmImpactDialog from "../../components/ConfirmImpactDialog.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const deployments = ref<Deployment[]>([]);
const dialogOpen = ref(false);
const selected = ref<Deployment | null>(null);
const operation = ref("pause");
const pendingOperation = ref<number | null>(null);

async function loadDeployments() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    deployments.value = (await consoleClient.listDeployments()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function openDialog(nextOperation: string, deployment: Deployment) {
  operation.value = nextOperation;
  selected.value = deployment;
  dialogOpen.value = true;
}

async function confirmOperation() {
  if (!selected.value) return;
  pendingOperation.value = selected.value.id;
  error.value = null;
  try {
    const updated = await consoleClient.controlDeployment(selected.value.id, operation.value);
    deployments.value = deployments.value.map((item) => (item.id === updated.id ? updated : item));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingOperation.value = null;
  }
  dialogOpen.value = false;
}

onMounted(loadDeployments);
</script>

<style scoped>
.ops {
  display: flex;
  gap: 8px;
}
</style>
