<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Platform</p>
        <h1 class="page-title">Provider Status</h1>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" />

    <div v-if="providers.length && !loading && !error" class="provider-grid">
      <section v-for="provider in providers" :key="provider.provider" class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">Provider</p>
            <h2>{{ provider.provider }}</h2>
          </div>
          <StatusBadge :status="provider.status" :label="provider.status" />
        </header>
        <div class="panel-body provider-body">
          <strong>{{ provider.summary }}</strong>
          <p>{{ provider.reason }}</p>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
  type ProviderStatus,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const providers = ref<ProviderStatus[]>([]);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    providers.value = await consoleClient.listProviderStatuses();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.provider-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.provider-body {
  display: grid;
  gap: 8px;
}

.provider-body p {
  margin: 0;
  color: var(--color-text-muted);
}

@media (max-width: 900px) {
  .provider-grid {
    grid-template-columns: 1fr;
  }
}
</style>
