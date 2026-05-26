<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("eventStore") }}</p>
        <h1 class="page-title">{{ t("events") }}</h1>
        <p class="page-subtitle">{{ t("eventsCopy") }}</p>
      </div>
    </header>
    <section class="panel">
      <div class="panel-body"><EventTimeline :events="events" /></div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { consoleClient } from "../../api/client";
import EventTimeline from "../../components/EventTimeline.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const events = consoleClient.listEvents().items;
</script>
