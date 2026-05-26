<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("agentVersionDeployment") }}</p>
        <h1 class="page-title">{{ t("agents") }}</h1>
        <p class="page-subtitle">{{ t("agentBoundary") }}</p>
      </div>
      <button class="button primary" type="button">{{ t("registerAgent") }}</button>
    </header>

    <div class="table-wrap">
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
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { agents } from "../../api/mockData";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>
