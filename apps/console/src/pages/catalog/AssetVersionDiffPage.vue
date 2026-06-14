<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Governance</p>
        <h1 class="page-title">Version diff</h1>
        <p class="page-subtitle">{{ detail?.item.name || kind }} · current v{{ detail?.item.version || "-" }}</p>
      </div>
      <RouterLink class="button" :to="detailTo">Back to detail</RouterLink>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="false" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="panel" :lines="8" />
    </section>

    <section v-if="detail" class="panel">
      <div class="panel-header">
        <div>
          <h2 class="panel-title">Changed fields</h2>
          <p class="panel-copy">Computed against the immediate previous version in the same asset family.</p>
        </div>
      </div>
      <div class="panel-body">
        <DataTable :columns="columns" :rows="detail.diff_to_previous.changed_fields" row-key="field" label="Changed fields">
          <template #cell-before="{ row }">
            <pre class="json-inline">{{ formatJson(row.before) }}</pre>
          </template>
          <template #cell-after="{ row }">
            <pre class="json-inline">{{ formatJson(row.after) }}</pre>
          </template>
        </DataTable>
        <p v-if="detail.diff_to_previous.changed_fields.length === 0" class="muted">No previous sibling diff is available yet.</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { AssetCatalogKind, AssetDetail } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import DataTable from "../../components/DataTable.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";

const props = defineProps<{
  kind: AssetCatalogKind;
  assetId: number;
  detailRouteName: string;
}>();

const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const detail = ref<AssetDetail | null>(null);

const columns = [
  { key: "field", label: "Field" },
  { key: "before", label: "Before" },
  { key: "after", label: "After" },
];

const detailTo = { name: props.detailRouteName, params: { assetId: props.assetId } };

function formatJson(value: unknown) {
  return JSON.stringify(value ?? null, null, 2);
}

async function loadDetail() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    detail.value = await consoleClient.getGovernedAssetDetail(props.kind, props.assetId);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadDetail();
});
</script>

<style scoped>
.json-inline {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.8rem;
}
</style>
