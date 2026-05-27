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
    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && events.length === 0" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { RuntimeEvent } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import EventTimeline from "../../components/EventTimeline.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const events = ref<RuntimeEvent[]>([]);

async function loadEvents() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    events.value = (await consoleClient.listEvents()).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(loadEvents);
</script>
