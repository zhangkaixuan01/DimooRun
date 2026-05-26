<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("publishedKicker") }}</p>
        <h1 class="page-title">{{ t("publishedSurfaces") }}</h1>
        <p class="page-subtitle">{{ t("publishedCopy") }}</p>
      </div>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr><th>{{ t("surface") }}</th><th>{{ t("type") }}</th><th>{{ t("deployment") }}</th><th>{{ t("auth") }}</th><th>{{ t("rateLimit") }}</th><th>{{ t("status") }}</th></tr></thead>
        <tbody>
          <tr><td class="mono">surf_api_support</td><td>Native API</td><td>dep_prod_support</td><td>api_key</td><td>500 rpm</td><td><StatusBadge status="active" label="active" /></td></tr>
          <tr><td class="mono">surf_lg_support</td><td>LangGraph-compatible</td><td>dep_prod_support</td><td>api_key</td><td>200 rpm</td><td><StatusBadge status="active" label="active" /></td></tr>
          <tr><td class="mono">surf_mcp_research</td><td>MCP server</td><td>dep_dev_research</td><td>internal</td><td>50 rpm</td><td><StatusBadge status="paused" label="paused" /></td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
</script>
