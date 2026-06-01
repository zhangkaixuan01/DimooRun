<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("agentVersionDeployment") }}</p>
        <h1 class="page-title">{{ t("agents") }}</h1>
        <p class="page-subtitle">{{ t("agentBoundary") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || creating" @click="createAgent">
        {{ creating ? t("creating") : t("registerAgent") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && agents.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && agents.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("agent") }}</th>
            <th>{{ t("framework") }}</th>
            <th>{{ t("adapter") }}</th>
            <th>{{ t("version") }}</th>
            <th>{{ t("capabilities") }}</th>
            <th>{{ t("deployments") }}</th>
            <th>{{ t("lastRun") }}</th>
            <th>{{ t("actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="agent in agents" :key="agent.id">
            <td><strong>{{ agent.name }}</strong><br /><span class="mono muted">{{ agent.id }}</span></td>
            <td>{{ agent.framework }}</td>
            <td>{{ agent.adapter }}</td>
            <td>{{ agent.version }}</td>
            <td>{{ agent.capabilities.join(", ") }}</td>
            <td>{{ agent.deployments }}</td>
            <td><StatusBadge :status="agent.lastRunStatus" :label="agent.lastRunStatus" /></td>
            <td><button class="button danger" type="button" :disabled="pendingAgent === agent.id" @click="archiveAgent(agent.id)">{{ t("disable") }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Agent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const creating = ref(false);
const error = ref<ConsoleApiError | null>(null);
const pendingAgent = ref<number | null>(null);
const agents = ref<Agent[]>([]);

async function loadAgents() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    agents.value = (await consoleClient.listAgents()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function createAgent() {
  creating.value = true;
  error.value = null;
  try {
    const agent = await consoleClient.createAgent({ name: `console-agent-${agents.value.length + 1}` });
    agents.value = [agent, ...agents.value];
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

async function archiveAgent(agentId: number) {
  pendingAgent.value = agentId;
  error.value = null;
  try {
    const agent = await consoleClient.archiveAgent(agentId);
    agents.value = agents.value.map((item) => (item.id === agent.id ? agent : item));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingAgent.value = null;
  }
}

onMounted(loadAgents);
</script>
