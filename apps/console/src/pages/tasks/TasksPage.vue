<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("leaseRetryDeadLetter") }}</p>
        <h1 class="page-title">{{ t("tasks") }}</h1>
      </div>
      <div class="toolbar">
        <select class="select"><option>{{ t("allQueues") }}</option><option>runtime.prod</option></select>
        <select class="select"><option>{{ t("allStatus") }}</option><option>leased</option><option>dead_letter</option></select>
      </div>
    </header>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ t("tasks") }}</th><th>{{ t("run") }}</th><th>{{ t("status") }}</th><th>{{ t("attempt") }}</th><th>{{ t("queue") }}</th><th>{{ t("worker") }}</th><th>{{ t("heartbeat") }}</th><th>{{ t("leaseUntil") }}</th><th>{{ t("fencing") }}</th><th>{{ t("retry") }}</th><th>{{ t("deadLetter") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td class="mono">{{ task.id }}</td>
            <td><ResourceLink :to="`/runs/${task.runId}`">{{ task.runId }}</ResourceLink></td>
            <td><StatusBadge :status="task.status" :label="task.status" /></td>
            <td>{{ task.attempt }}</td>
            <td>{{ task.queue }}</td>
            <td>{{ task.workerId }}</td>
            <td>{{ task.heartbeatAt }}</td>
            <td>{{ task.leaseUntil }}</td>
            <td>{{ task.fencingToken }}</td>
            <td>{{ task.retryCount }}</td>
            <td>{{ task.deadLetterReason ?? "-" }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { consoleClient } from "../../api/client";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const tasks = consoleClient.listTasks().items;
</script>
