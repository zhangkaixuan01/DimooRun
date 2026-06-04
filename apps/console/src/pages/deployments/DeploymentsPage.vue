<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("desiredWorkerHeartbeat") }}</p>
        <h1 class="page-title">{{ t("deployments") }}</h1>
        <p class="page-subtitle">{{ t("deploymentControlCopy") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || creatingDeployment" @click="openCreateDeployment">
        {{ t("createDeployment") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && deployments.length === 0" />

    <div v-if="mode !== 'offline' && !loading && !error && deployments.length > 0" class="table-wrap deployments-table">
      <table>
        <thead>
          <tr>
            <th>{{ t("deployment") }}</th>
            <th>{{ t("agent") }}</th>
            <th>{{ t("environment") }}</th>
            <th>{{ t("desiredStatus") }}</th>
            <th>{{ t("runtimeStatus") }}</th>
            <th>{{ t("instances") }}</th>
            <th>{{ t("backlog") }}</th>
            <th>{{ t("modelGateway") }}</th>
            <th>{{ t("operations") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="deployment in deployments"
            :key="deployment.id"
            class="deployment-row"
            :class="{ selected: selectedDeployment?.id === deployment.id }"
            :data-selected="selectedDeployment?.id === deployment.id ? 'true' : 'false'"
            tabindex="0"
            :aria-selected="selectedDeployment?.id === deployment.id"
            @click="selectDeployment(deployment)"
            @keydown.enter="selectDeployment(deployment)"
            @keydown.space.prevent="selectDeployment(deployment)"
          >
            <td class="mono">{{ deployment.id }}</td>
            <td>{{ deployment.agent }}@{{ deployment.version }}</td>
            <td>{{ deployment.environment }}</td>
            <td><StatusBadge :status="deployment.desiredStatus" :label="deployment.desiredStatus" /></td>
            <td><StatusBadge :status="deployment.runtimeStatus" :label="deployment.runtimeStatus" /></td>
            <td>{{ deployment.instances }}</td>
            <td>{{ deployment.queueBacklog }}</td>
            <td>{{ deployment.modelGateway }}</td>
            <td class="ops">
              <button class="button" type="button" :disabled="pendingOperation === deployment.id" @click.stop="openEditDeployment(deployment)">{{ t("edit") }}</button>
              <button class="button danger" type="button" :disabled="pendingOperation === deployment.id" @click.stop="openArchiveDeployment(deployment)">{{ t("archive") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <section v-if="mode !== 'offline' && !loading && !error && selectedDeployment" class="panel deployment-detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">{{ t("deployment") }}</p>
          <h2 class="panel-title">Deployment #{{ selectedDeployment.id }}</h2>
          <p class="muted">{{ selectedDeployment.agent }}@{{ selectedDeployment.version }} / {{ selectedDeployment.environment }}</p>
        </div>
        <div class="detail-actions">
          <button class="button" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openEditDeployment(selectedDeployment)">{{ t("edit") }}</button>
          <button class="button danger" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openArchiveDeployment(selectedDeployment)">{{ t("archive") }}</button>
        </div>
      </div>
      <div class="panel-body deployment-detail-layout">
        <aside class="deployment-summary">
          <dl>
            <div>
              <dt>{{ t("desiredStatus") }}</dt>
              <dd><StatusBadge :status="selectedDeployment.desiredStatus" :label="selectedDeployment.desiredStatus" /></dd>
            </div>
            <div>
              <dt>{{ t("runtimeStatus") }}</dt>
              <dd><StatusBadge :status="selectedDeployment.runtimeStatus" :label="selectedDeployment.runtimeStatus" /></dd>
            </div>
            <div class="metric-row">
              <div>
                <dt>{{ t("instances") }}</dt>
                <dd>{{ selectedDeployment.instances }}</dd>
              </div>
              <div>
                <dt>{{ t("backlog") }}</dt>
                <dd>{{ selectedDeployment.queueBacklog }}</dd>
              </div>
            </div>
            <div>
              <dt>{{ t("modelGateway") }}</dt>
              <dd>{{ selectedDeployment.modelGateway }}</dd>
            </div>
          </dl>
        </aside>

        <div class="child-workspace">
          <div class="detail-tabs" role="tablist" :aria-label="t('details')">
            <button class="tab-button" :class="{ active: activeDetailTab === 'control' }" type="button" role="tab" :aria-selected="activeDetailTab === 'control'" @click="activeDetailTab = 'control'">
              {{ t("operations") }}
            </button>
            <button class="tab-button" :class="{ active: activeDetailTab === 'task' }" type="button" role="tab" :aria-selected="activeDetailTab === 'task'" @click="activeDetailTab = 'task'">
              {{ t("submitDeploymentTask") }}
            </button>
          </div>

          <section v-if="activeDetailTab === 'control'" class="child-panel">
            <p class="muted">{{ t("deploymentControlCopy") }}</p>
            <div class="operation-grid">
              <button class="button" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('activate', selectedDeployment)">{{ t("activate") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('pause', selectedDeployment)">{{ t("pause") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('resume', selectedDeployment)">{{ t("resume") }}</button>
              <button class="button" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('drain', selectedDeployment)">{{ t("drain") }}</button>
              <button class="button danger" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('stop', selectedDeployment)">{{ t("stop") }}</button>
              <button class="button danger" type="button" :disabled="pendingOperation === selectedDeployment.id" @click="openDialog('restart', selectedDeployment)">{{ t("restart") }}</button>
            </div>
          </section>

          <form v-else class="child-panel" @submit.prevent="submitDeploymentTask">
            <p class="muted">{{ t("deploymentRequiredCopy") }}</p>
            <label>
              <span>{{ t("deploymentTaskInput") }}</span>
              <textarea v-model="deploymentTaskInputJson" class="textarea" rows="8"></textarea>
            </label>
            <label>
              <span>thread_id</span>
              <input v-model="deploymentTaskThreadId" class="input" />
            </label>
            <p v-if="taskInputError" class="form-error">{{ taskInputError }}</p>
            <button class="button primary" type="submit" :disabled="creatingTask || selectedDeployment.desiredStatus !== 'active'">
              {{ creatingTask ? t("creating") : t("submitDeploymentTask") }}
            </button>
            <p v-if="taskResult" class="muted">
              {{ t("taskCreated") }}:
              <ResourceLink :to="`/runs/${taskResult.runId}`">Run #{{ taskResult.runId }}</ResourceLink>
              / Task #{{ taskResult.taskId }}
            </p>
          </form>
        </div>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="createOpen" class="drawer-layer" @click.self="closeCreateDeployment">
        <aside class="drawer" :aria-label="t('createDeployment')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("deployment") }}</p>
              <h2>{{ t("createDeployment") }}</h2>
            </div>
          </header>
          <form class="drawer-form" @submit.prevent="createDeployment">
            <p v-if="agents.length === 0" class="muted">
              {{ t("deploymentNeedsAgentVersion") }}
              <RouterLink to="/agents">{{ t("agents") }}</RouterLink>
            </p>
            <p v-else-if="versions.length === 0" class="muted">{{ t("deploymentNeedsAgentVersion") }}</p>
            <label>
              <span>{{ t("agent") }}</span>
              <select v-model.number="deploymentForm.agentId" class="select" @change="loadVersionsForSelectedAgent">
                <option v-for="agent in agents" :key="agent.id" :value="agent.id">
                  {{ agent.name }} / {{ agent.id }}
                </option>
              </select>
            </label>
            <label>
              <span>{{ t("version") }}</span>
              <select v-model.number="deploymentForm.agentVersionId" class="select">
                <option v-for="version in versions" :key="version.id" :value="version.id">
                  {{ version.version }} / {{ version.status }}
                </option>
              </select>
            </label>
            <label>
              <span>{{ t("environment") }}</span>
              <input v-model="deploymentForm.environment" class="input" />
            </label>
            <label>
              <span>{{ t("replicas") }}</span>
              <input v-model.number="deploymentForm.replicas" class="input" min="1" type="number" />
            </label>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeCreateDeployment">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="creatingDeployment || !canCreateDeployment">
                {{ creatingDeployment ? t("creating") : t("createDeployment") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="editOpen" class="drawer-layer" @click.self="closeEditDeployment">
        <aside class="drawer" :aria-label="t('editDeployment')" role="dialog" aria-modal="true">
          <header class="drawer-header">
            <div>
              <p class="page-kicker">{{ t("deployment") }} #{{ editDeploymentForm.id }}</p>
              <h2>{{ t("editDeployment") }}</h2>
            </div>
          </header>
          <form class="drawer-form" @submit.prevent="updateDeployment">
            <label>
              <span>{{ t("version") }}</span>
              <select v-model.number="editDeploymentForm.agentVersionId" class="select">
                <option v-for="version in editVersions" :key="version.id" :value="version.id">
                  {{ version.version }} / {{ version.status }}
                </option>
              </select>
            </label>
            <label>
              <span>{{ t("environment") }}</span>
              <input v-model="editDeploymentForm.environment" class="input" required />
            </label>
            <label>
              <span>{{ t("replicas") }}</span>
              <input v-model.number="editDeploymentForm.replicas" class="input" min="1" required type="number" />
            </label>
            <label>
              <span>{{ t("config") }}</span>
              <textarea v-model="editDeploymentForm.configJson" class="textarea" rows="10"></textarea>
            </label>
            <p v-if="editError" class="form-error">{{ editError }}</p>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeEditDeployment">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="updatingDeployment || !canUpdateDeployment">
                {{ updatingDeployment ? t("saving") : t("save") }}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </Teleport>

    <DangerConfirmDialog
      :open="Boolean(archiveTarget)"
      :title="t('archiveDeployment')"
      :message="t('archiveDeploymentCopy')"
      :items="archiveConfirmItems"
      :confirm-label="t('archive')"
      :cancel-label="t('cancel')"
      :busy-label="t('saving')"
      :busy="archivingDeployment"
      :error="archiveError"
      @cancel="closeArchiveDeployment"
      @confirm="archiveDeployment"
    />

    <ConfirmImpactDialog
      v-if="selected"
      :open="dialogOpen"
      :title="`${operation} ${selected.id}`"
      :impact-target="String(selected.id)"
      :environment="selected.environment"
      :affects-new-runs="operation !== 'restart'"
      :affects-existing-runs="operation === 'restart'"
      :writes-audit-log="true"
      :rollbackable="operation !== 'restart'"
      @cancel="dialogOpen = false"
      @confirm="confirmOperation"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Agent, AgentVersion, Deployment, TaskCreateResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import ConfirmImpactDialog from "../../components/ConfirmImpactDialog.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const mode = apiMode();
const loading = ref(false);
const error = ref<ConsoleApiError | null>(null);
const agents = ref<Agent[]>([]);
const versions = ref<AgentVersion[]>([]);
const deployments = ref<Deployment[]>([]);
const dialogOpen = ref(false);
const selected = ref<Deployment | null>(null);
const selectedDeployment = ref<Deployment | null>(null);
const operation = ref("pause");
const pendingOperation = ref<number | null>(null);
const creatingDeployment = ref(false);
const updatingDeployment = ref(false);
const archivingDeployment = ref(false);
const creatingTask = ref(false);
const createOpen = ref(false);
const activeDetailTab = ref<"control" | "task">("control");
const deploymentTaskInputJson = ref('{\n  "message": "hello"\n}');
const deploymentTaskThreadId = ref("");
const taskInputError = ref("");
const editError = ref("");
const taskResult = ref<TaskCreateResult | null>(null);
const editOpen = ref(false);
const editVersions = ref<AgentVersion[]>([]);
const archiveTarget = ref<Deployment | null>(null);
const archiveError = ref<ConsoleApiError | null>(null);
const deploymentForm = reactive({
  agentId: null as number | null,
  agentVersionId: null as number | null,
  environment: "production",
  replicas: 1,
});
const editDeploymentForm = reactive({
  id: null as number | null,
  agentId: null as number | null,
  agentVersionId: null as number | null,
  environment: "",
  replicas: 1,
  configJson: "{}",
});

const canCreateDeployment = computed(() => Boolean(deploymentForm.agentId && deploymentForm.agentVersionId && deploymentForm.environment && deploymentForm.replicas > 0));
const canUpdateDeployment = computed(() => Boolean(editDeploymentForm.id && editDeploymentForm.agentVersionId && editDeploymentForm.environment && editDeploymentForm.replicas > 0));
const archiveConfirmItems = computed(() => archiveTarget.value ? [
  { label: t("deployment"), value: String(archiveTarget.value.id) },
  { label: t("agent"), value: `${archiveTarget.value.agent}@${archiveTarget.value.version}` },
  { label: t("environment"), value: archiveTarget.value.environment },
] : []);

async function loadRuntimeEntry() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    const [agentPage, deploymentPage] = await Promise.all([
      consoleClient.listAgents(),
      consoleClient.listDeployments(),
    ]);
    agents.value = agentPage.items;
    deployments.value = deploymentPage.items;
    if (!selectedDeployment.value && deployments.value[0]) {
      selectDeployment(deployments.value[0]);
    } else if (selectedDeployment.value) {
      selectedDeployment.value = deployments.value.find((item) => item.id === selectedDeployment.value?.id) ?? deployments.value[0] ?? null;
    }
    if (!deploymentForm.agentId && agents.value[0]) {
      deploymentForm.agentId = agents.value[0].id;
      await loadVersionsForSelectedAgent();
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function resetDeploymentForm() {
  deploymentForm.agentId = agents.value[0]?.id ?? null;
  deploymentForm.agentVersionId = null;
  deploymentForm.environment = "production";
  deploymentForm.replicas = 1;
}

async function openCreateDeployment() {
  resetDeploymentForm();
  createOpen.value = true;
  if (deploymentForm.agentId) {
    await loadVersionsForSelectedAgent();
  }
}

function closeCreateDeployment() {
  if (creatingDeployment.value) return;
  createOpen.value = false;
}

function selectDeployment(deployment: Deployment) {
  selectedDeployment.value = deployment;
  activeDetailTab.value = "control";
  taskResult.value = null;
  taskInputError.value = "";
}

async function loadVersionsForSelectedAgent() {
  if (!deploymentForm.agentId) {
    versions.value = [];
    deploymentForm.agentVersionId = null;
    return;
  }
  error.value = null;
  try {
    versions.value = (await consoleClient.listAgentVersions(deploymentForm.agentId)).items;
    deploymentForm.agentVersionId = versions.value[0]?.id ?? null;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
}

async function createDeployment() {
  if (!canCreateDeployment.value || !deploymentForm.agentId || !deploymentForm.agentVersionId) return;
  creatingDeployment.value = true;
  error.value = null;
  try {
    const deployment = await consoleClient.createDeployment({
      agent_id: deploymentForm.agentId,
      agent_version_id: deploymentForm.agentVersionId,
      environment: deploymentForm.environment,
      desired_status: "draft",
      replicas: deploymentForm.replicas,
      config: {},
    });
    deployments.value = [deployment, ...deployments.value.filter((item) => item.id !== deployment.id)];
    selectDeployment(deployment);
    createOpen.value = false;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingDeployment.value = false;
  }
}

async function openEditDeployment(deployment: Deployment) {
  editError.value = "";
  error.value = null;
  editDeploymentForm.id = deployment.id;
  editDeploymentForm.agentId = Number(deployment.agent);
  editDeploymentForm.agentVersionId = Number(deployment.version);
  editDeploymentForm.environment = deployment.environment;
  editDeploymentForm.replicas = deployment.instances;
  editDeploymentForm.configJson = JSON.stringify(deployment.config ?? {}, null, 2);
  editOpen.value = true;
  try {
    editVersions.value = (await consoleClient.listAgentVersions(Number(deployment.agent))).items;
  } catch (caught) {
    error.value = toConsoleApiError(caught);
    editVersions.value = [];
  }
}

function closeEditDeployment() {
  editOpen.value = false;
  editError.value = "";
  editVersions.value = [];
}

async function updateDeployment() {
  if (!canUpdateDeployment.value || !editDeploymentForm.id || !editDeploymentForm.agentVersionId) return;
  const config = parseConfigInput();
  if (!config) return;
  updatingDeployment.value = true;
  error.value = null;
  try {
    const updated = await consoleClient.updateDeployment(editDeploymentForm.id, {
      agent_version_id: editDeploymentForm.agentVersionId,
      environment: editDeploymentForm.environment,
      replicas: editDeploymentForm.replicas,
      config,
    });
    deployments.value = deployments.value.map((item) => (item.id === updated.id ? updated : item));
    if (selectedDeployment.value?.id === updated.id) {
      selectedDeployment.value = updated;
    }
    closeEditDeployment();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    updatingDeployment.value = false;
  }
}

function parseConfigInput(): Record<string, unknown> | null {
  editError.value = "";
  try {
    const parsed = JSON.parse(editDeploymentForm.configJson);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      editError.value = t("jsonObjectRequired");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    editError.value = t("invalidJson");
    return null;
  }
}

function openArchiveDeployment(deployment: Deployment) {
  archiveTarget.value = deployment;
  archiveError.value = null;
}

function closeArchiveDeployment() {
  if (archivingDeployment.value) return;
  archiveTarget.value = null;
  archiveError.value = null;
}

async function archiveDeployment() {
  if (!archiveTarget.value) return;
  archivingDeployment.value = true;
  archiveError.value = null;
  try {
    const archived = await consoleClient.archiveDeployment(archiveTarget.value.id);
    deployments.value = deployments.value.filter((item) => item.id !== archived.id);
    if (selectedDeployment.value?.id === archived.id) {
      selectedDeployment.value = deployments.value[0] ?? null;
    }
    archiveTarget.value = null;
  } catch (caught) {
    archiveError.value = toConsoleApiError(caught);
  } finally {
    archivingDeployment.value = false;
  }
}

async function submitDeploymentTask() {
  if (!selectedDeployment.value) return;
  const input = parseTaskInput();
  if (!input) return;
  creatingTask.value = true;
  error.value = null;
  try {
    taskResult.value = await consoleClient.createDeploymentTask(selectedDeployment.value.id, {
      input,
      thread_id: deploymentTaskThreadId.value || undefined,
    });
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingTask.value = false;
  }
}

function parseTaskInput(): Record<string, unknown> | null {
  taskInputError.value = "";
  try {
    const parsed = JSON.parse(deploymentTaskInputJson.value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      taskInputError.value = t("jsonObjectRequired");
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    taskInputError.value = t("invalidJson");
    return null;
  }
}

function openDialog(nextOperation: string, deployment: Deployment) {
  operation.value = nextOperation;
  selected.value = deployment;
  dialogOpen.value = true;
}

async function confirmOperation() {
  if (!selected.value) return;
  pendingOperation.value = selected.value.id;
  error.value = null;
  try {
    const updated = await consoleClient.controlDeployment(selected.value.id, operation.value);
    deployments.value = deployments.value.map((item) => (item.id === updated.id ? updated : item));
    if (selectedDeployment.value?.id === updated.id) {
      selectedDeployment.value = updated;
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingOperation.value = null;
  }
  dialogOpen.value = false;
}

onMounted(loadRuntimeEntry);
</script>

<style scoped>
.deployments-table tbody tr.deployment-row {
  cursor: pointer;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.deployments-table tbody tr.deployment-row td {
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.deployments-table tbody tr.deployment-row:hover,
.deployments-table tbody tr.deployment-row:focus-visible {
  background: color-mix(in oklab, var(--color-primary) 8%, transparent);
  outline: none;
}

.deployments-table tbody tr.deployment-row.selected,
.deployments-table tbody tr.deployment-row[data-selected="true"] {
  background: var(--color-accent-soft);
}

.deployments-table tbody tr.deployment-row.selected td,
.deployments-table tbody tr.deployment-row[data-selected="true"] td {
  background: var(--color-accent-soft) !important;
}

.deployments-table tbody tr.deployment-row.selected td:first-child,
.deployments-table tbody tr.deployment-row[data-selected="true"] td:first-child {
  box-shadow: inset 3px 0 0 var(--color-primary) !important;
}

.deployment-detail-panel {
  margin-bottom: 16px;
  margin-top: 16px;
}

.section-kicker {
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0;
  margin: 0 0 4px;
  text-transform: uppercase;
}

.detail-actions,
.ops {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.deployment-detail-layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 16px;
}

.deployment-summary {
  display: grid;
  align-content: start;
  border-right: 1px solid var(--color-border);
  padding-right: 16px;
}

.deployment-summary dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

.deployment-summary dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.deployment-summary dd {
  margin: 0;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-row dd {
  font-size: 1.35rem;
  font-weight: 800;
}

.child-workspace {
  min-width: 0;
}

.detail-tabs {
  display: inline-flex;
  gap: 4px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 4px;
}

.tab-button {
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font: inherit;
  font-weight: 800;
  min-height: 34px;
  padding: 7px 12px;
}

.tab-button:hover,
.tab-button:focus-visible {
  color: var(--color-text);
  outline: none;
}

.tab-button.active {
  background: var(--color-surface);
  box-shadow: var(--shadow-card);
  color: var(--color-text);
}

.child-panel {
  display: grid;
  align-content: start;
  gap: 12px;
  margin-top: 14px;
}

.operation-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text);
  padding: 10px 12px;
  font: inherit;
}

.form-error {
  margin: 0;
  color: var(--color-danger);
  font-weight: 700;
}

.drawer-layer {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  justify-content: flex-end;
  background: oklch(18% 0.017 248 / 36%);
}

.drawer {
  display: grid;
  width: min(480px, 100%);
  grid-template-rows: auto 1fr;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 18px;
}

.drawer-header h2 {
  margin: 0;
  font-size: 19px;
  line-height: 1.2;
}

.drawer-form {
  display: grid;
  align-content: start;
  gap: 14px;
  overflow: auto;
  padding: 18px;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  margin: 8px -18px -18px;
  padding: 14px 18px;
}

@media (max-width: 900px) {
  .deployment-detail-layout,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .deployment-summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 14px;
  }

  .drawer {
    width: 100%;
  }
}
</style>
