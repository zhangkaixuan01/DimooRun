<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">Runtime Operations</p>
        <h1 class="page-title">Agent Instances</h1>
        <p class="page-subtitle">
          Worker assignment, concurrency limits, runtime config hashes, and recent failures.
        </p>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && instances.length === 0" />

    <div v-if="mode !== 'offline' && !loading && instances.length > 0" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Instance</th>
            <th>Deployment</th>
            <th>Worker</th>
            <th>Status</th>
            <th>Active runs</th>
            <th>Recent failures</th>
            <th>Concurrency</th>
            <th>Config hash</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="instance in instances"
            :key="instance.id"
            class="selectable-row"
            :data-selected="selectedInstance?.id === instance.id ? 'true' : 'false'"
            tabindex="0"
            @click="selectInstance(instance.id)"
            @keydown.enter="selectInstance(instance.id)"
            @keydown.space.prevent="selectInstance(instance.id)"
          >
            <td class="mono">{{ instance.id }}</td>
            <td>{{ instance.deploymentId }}</td>
            <td>{{ instance.workerId }}</td>
            <td><StatusBadge :status="instance.status === 'ready' ? 'ready' : 'degraded'" :label="instance.status" /></td>
            <td>{{ instance.activeRuns }}</td>
            <td>{{ instance.recentFailures }}</td>
            <td>{{ instance.concurrencyLimit }}</td>
            <td class="mono">{{ instance.runtimeConfigHash }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="selectedInstance" class="panel detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">Instance detail</p>
          <h2 class="panel-title">Instance #{{ selectedInstance.id }}</h2>
          <p class="muted">{{ selectedInstance.environment }} / {{ selectedInstance.status }}</p>
        </div>
      </div>
      <div class="panel-body detail-grid">
        <div class="summary">
          <dl>
            <div>
              <dt>Deployment</dt>
              <dd>
                <ResourceLink :to="`/deployments/${selectedInstance.deploymentId}`">
                  Deployment #{{ selectedInstance.deploymentId }}
                </ResourceLink>
              </dd>
            </div>
            <div>
              <dt>Worker</dt>
              <dd>
                <ResourceLink :to="`/runtime/workers?worker=${encodeURIComponent(selectedInstance.workerId)}`">
                  {{ selectedInstance.workerId }}
                </ResourceLink>
              </dd>
            </div>
            <div>
              <dt>Desired / runtime</dt>
              <dd>
                {{ selectedInstance.deploymentDesiredStatus }} / {{ selectedInstance.deploymentRuntimeStatus }}
              </dd>
            </div>
            <div>
              <dt>Execution profile</dt>
              <dd>{{ selectedInstance.executionProfileId || "default" }}</dd>
            </div>
          </dl>
        </div>
        <div class="workspace">
          <section class="child-panel">
            <h3>Runtime state</h3>
            <dl class="metrics">
              <div>
                <dt>Active runs</dt>
                <dd>{{ selectedInstance.activeRuns }}</dd>
              </div>
              <div>
                <dt>Recent failures</dt>
                <dd>{{ selectedInstance.recentFailures }}</dd>
              </div>
              <div>
                <dt>Concurrency limit</dt>
                <dd>{{ selectedInstance.concurrencyLimit }}</dd>
              </div>
              <div>
                <dt>Runtime config hash</dt>
                <dd class="mono">{{ selectedInstance.runtimeConfigHash }}</dd>
              </div>
            </dl>
          </section>
          <section class="child-panel">
            <h3>Lifecycle</h3>
            <p class="muted">Loaded: {{ selectedInstance.loadedAt || "n/a" }}</p>
            <p class="muted">Heartbeat: {{ selectedInstance.heartbeatAt || "n/a" }}</p>
            <p v-if="selectedInstance.lastError" class="form-error">
              {{ selectedInstance.lastError }}
            </p>
          </section>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
} from "../../api/client";
import type { RuntimeAgentInstance, RuntimeAgentInstanceDetail } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";

const route = useRoute();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const instances = ref<RuntimeAgentInstance[]>([]);
const selectedInstance = ref<RuntimeAgentInstanceDetail | null>(null);

async function loadInstances(selectedId?: number) {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    instances.value = (await consoleClient.listRuntimeAgentInstances()).items;
    const nextId = selectedId || Number(route.query.instance || 0) || instances.value[0]?.id;
    if (nextId) {
      await selectInstance(nextId);
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function selectInstance(instanceId: number) {
  try {
    selectedInstance.value = await consoleClient.getRuntimeAgentInstance(instanceId);
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
}

onMounted(async () => {
  await loadInstances();
});
</script>

<style scoped>
.selectable-row {
  cursor: pointer;
}

.selectable-row[data-selected="true"] {
  background: var(--color-accent-soft);
}

.detail-panel {
  margin-top: 16px;
}

.section-kicker {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  text-transform: uppercase;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 16px;
}

.summary {
  border-right: 1px solid var(--color-border);
  padding-right: 16px;
}

.summary dl,
.workspace,
.child-panel {
  display: grid;
  gap: 12px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.summary dt,
.metrics dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
}

.summary dd,
.metrics dd {
  margin: 4px 0 0;
}

@media (max-width: 900px) {
  .detail-grid,
  .metrics {
    grid-template-columns: 1fr;
  }

  .summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 16px;
  }
}
</style>
