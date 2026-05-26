<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("approvalResume") }}</p>
        <h1 class="page-title">{{ t("humanTasks") }}</h1>
      </div>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr><th>{{ t("tasks") }}</th><th>{{ t("source") }}</th><th>{{ t("risk") }}</th><th>{{ t("status") }}</th><th>{{ t("assignee") }}</th><th>{{ t("expires") }}</th><th>{{ t("actions") }}</th></tr></thead>
        <tbody>
          <tr v-for="task in humanTasks" :key="task.id">
            <td class="mono">{{ task.id }}</td>
            <td>{{ task.source }}</td>
            <td><StatusBadge :status="task.risk === 'critical' ? 'failed' : 'pending'" :label="task.risk" /></td>
            <td><StatusBadge :status="task.status" :label="task.status" /></td>
            <td>{{ task.assignee }}</td>
            <td>{{ task.expiresAt }}</td>
            <td class="ops"><button class="button" type="button">{{ t("approve") }}</button><button class="button danger" type="button">{{ t("reject") }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { humanTasks } from "../../api/mockData";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>

<style scoped>
.ops {
  display: flex;
  gap: 8px;
}
</style>
