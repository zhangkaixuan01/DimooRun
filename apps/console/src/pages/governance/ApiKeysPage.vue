<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("machineIdentity") }}</p>
        <h1 class="page-title">{{ t("apiKeys") }}</h1>
        <p class="page-subtitle">{{ t("apiKeysCopy") }}</p>
      </div>
      <button class="button primary" type="button">{{ t("createApiKey") }}</button>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr><th>{{ t("name") }}</th><th>{{ t("prefix") }}</th><th>{{ t("scopes") }}</th><th>{{ t("status") }}</th><th>{{ t("lastUsed") }}</th><th>{{ t("actions") }}</th></tr></thead>
        <tbody>
          <tr>
            <td>support-prod</td><td class="mono">dmrk_live_8f2...</td><td>runs:create, runs:read</td><td><StatusBadge status="active" label="active" /></td><td>2026-05-26T09:20:00Z</td><td><button class="button danger" type="button">{{ t("disable") }}</button></td>
          </tr>
          <tr>
            <td>compat-langgraph</td><td class="mono">dmrk_live_a10...</td><td>compat:assistants, compat:runs</td><td><StatusBadge status="active" label="active" /></td><td>2026-05-26T08:58:00Z</td><td><button class="button danger" type="button">{{ t("disable") }}</button></td>
          </tr>
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
