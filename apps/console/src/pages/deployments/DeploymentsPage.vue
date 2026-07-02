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

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="table" :lines="8" />
      <SkeletonBlock :lines="6" />
    </section>

    <DataTable
      v-if="mode !== 'offline' && !loading && deployments.length > 0"
      class="deployments-table"
      :columns="deploymentColumns"
      :rows="deployments"
      row-key="id"
      :selected-key="selectedDeployment?.id ?? null"
      :label="t('deployments')"
      selectable
      @row-select="selectDeploymentRow"
    >
      <template #cell-deployment="{ row }">
        <span class="mono">{{ row.id }}</span>
      </template>
      <template #cell-agentVersion="{ row }">
        {{ row.agent }}@{{ row.version }}
      </template>
      <template #cell-desiredStatus="{ row }">
        <StatusBadge :status="row.desiredStatus" :label="row.desiredStatus" />
      </template>
      <template #cell-runtimeStatus="{ row }">
        <StatusBadge :status="row.runtimeStatus" :label="row.runtimeStatus" />
      </template>
      <template #cell-operations="{ row }">
        <div class="ops">
          <button class="button" type="button" :disabled="pendingOperation === row.id" @click.stop="openEditDeployment(row)">{{ t("edit") }}</button>
          <button class="button danger" type="button" :disabled="pendingOperation === row.id" @click.stop="openArchiveDeployment(row)">{{ t("archive") }}</button>
        </div>
      </template>
    </DataTable>

    <section v-if="mode !== 'offline' && !loading && selectedDeployment" class="panel deployment-detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">{{ t("deployment") }}</p>
          <h2 class="panel-title">{{ t("deployment") }} #{{ selectedDeployment.id }}</h2>
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
            <button class="tab-button" :class="{ active: activeDetailTab === 'promotion' }" type="button" role="tab" :aria-selected="activeDetailTab === 'promotion'" @click="openPromotionTab">
              {{ t("promotion") }}
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

          <form v-else-if="activeDetailTab === 'task'" class="child-panel" @submit.prevent="submitDeploymentTask">
            <p class="muted">{{ t("deploymentRequiredCopy") }}</p>
            <JsonSchemaEditor
              v-model="deploymentTaskInputJson"
              :label="t('deploymentTaskInput')"
              :error="taskInputError"
              :rows="8"
            />
            <label>
              <span>{{ t("threadId") }}</span>
              <input v-model="deploymentTaskThreadId" class="input" />
            </label>
            <button class="button primary" type="submit" :disabled="creatingTask || selectedDeployment.desiredStatus !== 'active'">
              {{ creatingTask ? t("creating") : t("submitDeploymentTask") }}
            </button>
            <p v-if="taskResult" class="muted">
              {{ t("taskCreated") }}:
              <ResourceLink :to="`/runs/${taskResult.runId}`">Run #{{ taskResult.runId }}</ResourceLink>
              / Task #{{ taskResult.taskId }}
            </p>
          </form>

          <section v-else class="child-panel promotion-panel">
            <p class="muted">{{ t("deploymentPromotionCopy") }}</p>
            <div class="form-grid">
              <label>
                <span>{{ t("candidateVersion") }}</span>
                <select v-model.number="promotionCandidateVersionId" class="select">
                  <option v-for="version in promotionVersions" :key="version.id" :value="version.id">
                    {{ version.version }} / {{ version.status }}
                  </option>
                </select>
              </label>
              <label>
                <span>{{ t("experimentRun") }}</span>
                <input v-model.number="promotionExperimentRunId" class="input" min="1" type="number" />
              </label>
              <label>
                <span>{{ t("rolloutReason") }}</span>
                <input v-model="rolloutReason" class="input" />
              </label>
            </div>
            <div class="operation-grid">
              <button class="button" type="button" :disabled="previewingPromotion || !promotionCandidateVersionId || !promotionExperimentRunId" @click="previewPromotion">
                {{ previewingPromotion ? t("previewing") : t("previewPromotion") }}
              </button>
              <button class="button primary" type="button" :disabled="promotingDeployment || !canPromoteDeployment" @click="promoteDeployment">
                {{ promotingDeployment ? t("promoting") : t("promoteCandidate") }}
              </button>
            </div>
            <section v-if="promotionPreview" class="impact-preview" :aria-label="t('impactPreview')">
              <h3>{{ t("impactPreview") }}</h3>
              <p class="muted">{{ promotionPreview.currentAgentVersionId }} -> {{ promotionPreview.candidateAgentVersionId }}</p>
              <dl>
                <div>
                  <dt>{{ t("currentVersion") }}</dt>
                  <dd>{{ promotionPreview.currentAgentVersionId }}</dd>
                </div>
                <div>
                  <dt>{{ t("candidateVersion") }}</dt>
                  <dd>{{ promotionPreview.candidateAgentVersionId }}</dd>
                </div>
                <div>
                  <dt>{{ t("activeRuns") }}</dt>
                  <dd>{{ promotionPreview.activeRuns }}</dd>
                </div>
                <div>
                  <dt>{{ t("queuedTasks") }}</dt>
                  <dd>{{ promotionPreview.queuedTasks }}</dd>
                </div>
                <div>
                  <dt>{{ t("candidateStatus") }}</dt>
                  <dd>{{ promotionPreview.candidateValidationStatus }}</dd>
                </div>
                <div>
                  <dt>{{ t("rollbackTarget") }}</dt>
                  <dd>{{ promotionPreview.rollbackAgentVersionId || t("none") }}</dd>
                </div>
                <div>
                  <dt>{{ t("experimentRun") }}</dt>
                  <dd>{{ promotionExperimentRunId || t("none") }}</dd>
                </div>
              </dl>
              <p v-if="promotionPreview.qualityGate" class="muted">
                {{ t("qualityGate") }}: {{ String(promotionPreview.qualityGate.status || "-") }}
              </p>
              <p v-if="promotionPreview.qualityGate && promotionPreview.qualityGate.blocked_reason" class="form-error">
                {{ String(promotionPreview.qualityGate.blocked_reason) }}
              </p>
              <p v-if="promotionPreview.blockedReason" class="form-error">{{ promotionPreview.blockedReason }}</p>
              <p v-for="warning in promotionPreview.warnings" :key="warning" class="muted">{{ warning }}</p>
            </section>
            <p v-if="promotionMessage" class="muted">{{ promotionMessage }}</p>
            <label>
              <span>{{ t("rollbackReason") }}</span>
              <input v-model="rollbackReason" class="input" />
            </label>
            <button class="button danger" type="button" :disabled="rollingBackDeployment || !canRollbackDeployment" @click="rollbackDeployment">
              {{ rollingBackDeployment ? t("rollingBack") : t("rollback") }}
            </button>
          </section>
        </div>
      </div>
    </section>

    <AppDrawer
      :open="createOpen"
      :label="t('createDeployment')"
      :title="t('createDeployment')"
      :kicker="t('deployment')"
      @close="closeCreateDeployment"
    >
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
    </AppDrawer>

    <AppDrawer
      :open="editOpen"
      :label="t('editDeployment')"
      :title="t('editDeployment')"
      :kicker="`${t('deployment')} #${editDeploymentForm.id ?? ''}`"
      @close="closeEditDeployment"
    >
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
            <JsonSchemaEditor
              v-model="editDeploymentForm.configJson"
              :label="t('config')"
              :error="editConfigError"
              :rows="10"
            />
            <p v-if="editError" class="form-error">{{ editError }}</p>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeEditDeployment">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="updatingDeployment || !canUpdateDeployment">
                {{ updatingDeployment ? t("saving") : t("save") }}
              </button>
            </div>
      </form>
    </AppDrawer>

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
import { useRoute } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import { createMutationAction } from "../../api/mutations";
import { createQueryResource } from "../../api/query";
import type { Agent, AgentVersion, Deployment, DeploymentPromotionPreview, TaskCreateResult } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import ConfirmImpactDialog from "../../components/ConfirmImpactDialog.vue";
import DataTable from "../../components/DataTable.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import JsonSchemaEditor from "../../components/JsonSchemaEditor.vue";
import ResourceLink from "../../components/ResourceLink.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { isJsonParseFailure, parseJsonObject, type JsonParseFailure } from "../../forms/jsonForm";
import { validateDeploymentConfig } from "../../forms/validators";
import { useI18n } from "../../i18n/useI18n";

const { t } = useI18n();
const route = useRoute();
const props = defineProps<{
  initialDeploymentId?: string | number;
}>();
const mode = apiMode();
const pageError = ref<ConsoleApiError | null>(null);
const agents = ref<Agent[]>([]);
const versions = ref<AgentVersion[]>([]);
const deployments = ref<Deployment[]>([]);
const dialogOpen = ref(false);
const selected = ref<Deployment | null>(null);
const selectedDeployment = ref<Deployment | null>(null);
const operation = ref("pause");
const pendingOperation = ref<number | null>(null);
const createOpen = ref(false);
const activeDetailTab = ref<"control" | "task" | "promotion">("control");
const deploymentTaskInputJson = ref('{\n  "message": "hello"\n}');
const deploymentTaskThreadId = ref("");
const taskInputError = ref<JsonParseFailure | null>(null);
const editError = ref("");
const taskResult = ref<TaskCreateResult | null>(null);
const promotionVersions = ref<AgentVersion[]>([]);
const promotionCandidateVersionId = ref<number | null>(null);
const promotionExperimentRunId = ref<number | null>(null);
const promotionPreview = ref<DeploymentPromotionPreview | null>(null);
const rolloutReason = ref("");
const rollbackReason = ref("");
const promotionMessage = ref("");
const editOpen = ref(false);
const editVersions = ref<AgentVersion[]>([]);
const archiveTarget = ref<Deployment | null>(null);
const editConfigError = ref<JsonParseFailure | null>(null);
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
const deploymentColumns = computed(() => [
  { key: "deployment", label: t("deployment") },
  { key: "agentVersion", label: t("agent") },
  { key: "environment", label: t("environment") },
  { key: "desiredStatus", label: t("desiredStatus") },
  { key: "runtimeStatus", label: t("runtimeStatus") },
  { key: "instances", label: t("instances"), align: "center" as const },
  { key: "queueBacklog", label: t("backlog"), align: "center" as const },
  { key: "modelGateway", label: t("modelGateway") },
  { key: "operations", label: t("operations") },
]);
const runtimeQuery = createQueryResource(async () => {
  if (mode === "offline") {
    return { agents: [] as Agent[], deployments: [] as Deployment[] };
  }
  const [agentPage, deploymentPage] = await Promise.all([
    consoleClient.listAgents(),
    consoleClient.listDeployments(),
  ]);
  return {
    agents: agentPage.items,
    deployments: deploymentPage.items,
  };
});
const loading = computed(() => runtimeQuery.loading.value);
const error = computed(() => pageError.value ?? (runtimeQuery.error.value ? toConsoleApiError(runtimeQuery.error.value) : null));
const creatingDeployment = computed(() => createDeploymentMutation.busy.value);
const updatingDeployment = computed(() => updateDeploymentMutation.busy.value);
const archivingDeployment = computed(() => archiveDeploymentMutation.busy.value);
const creatingTask = computed(() => createTaskMutation.busy.value);
const previewingPromotion = computed(() => promotionPreviewMutation.busy.value);
const promotingDeployment = computed(() => promoteDeploymentMutation.busy.value);
const rollingBackDeployment = computed(() => rollbackDeploymentMutation.busy.value);
const archiveError = computed(() => archiveDeploymentMutation.error.value);
const canPromoteDeployment = computed(() => Boolean(
  selectedDeployment.value
  && promotionCandidateVersionId.value
  && promotionExperimentRunId.value
  && promotionPreview.value
  && promotionPreview.value.canPromote
  && rolloutReason.value.trim(),
));
const canRollbackDeployment = computed(() => Boolean(
  selectedDeployment.value
  && promotionPreview.value?.rollbackAgentVersionId
  && rollbackReason.value.trim(),
));

const createDeploymentMutation = createMutationAction(
  async (_payload: void, context) => {
    if (!deploymentForm.agentId || !deploymentForm.agentVersionId) {
      throw new Error("Deployment requires agent and version.");
    }
    return consoleClient.createDeployment({
      agent_id: deploymentForm.agentId,
      agent_version_id: deploymentForm.agentVersionId,
      environment: deploymentForm.environment,
      desired_status: "draft",
      replicas: deploymentForm.replicas,
      config: {},
    }, context);
  },
  { reload: loadRuntimeEntry },
);
const updateDeploymentMutation = createMutationAction(
  async (payload: { id: number; agentVersionId: number; environment: string; replicas: number; config: Record<string, unknown> }, context) =>
    consoleClient.updateDeployment(payload.id, {
      agent_version_id: payload.agentVersionId,
      environment: payload.environment,
      replicas: payload.replicas,
      config: payload.config,
    }, context),
  { reload: loadRuntimeEntry },
);
const archiveDeploymentMutation = createMutationAction(
  async (deployment: Deployment, context) => consoleClient.archiveDeployment(deployment.id, context),
  { reload: loadRuntimeEntry },
);
const controlDeploymentMutation = createMutationAction(
  async (payload: { deployment: Deployment; operation: string }, context) => consoleClient.controlDeployment(payload.deployment.id, payload.operation, context),
  { reload: loadRuntimeEntry },
);
const promotionPreviewMutation = createMutationAction(
  async (payload: { deployment: Deployment; candidateVersionId: number; experimentRunId: number }) =>
    consoleClient.getDeploymentPromotionPreview(
      payload.deployment.id,
      payload.candidateVersionId,
      payload.experimentRunId,
    ),
);
const promoteDeploymentMutation = createMutationAction(
  async (payload: { deployment: Deployment; candidateVersionId: number; expectedCurrentVersionId: number; experimentRunId: number; reason: string }, context) =>
    consoleClient.promoteDeployment(payload.deployment.id, {
      candidate_version_id: payload.candidateVersionId,
      expected_current_version_id: payload.expectedCurrentVersionId,
      experiment_run_id: payload.experimentRunId,
      rollout_reason: payload.reason,
    }, context),
  { reload: loadRuntimeEntry },
);
const rollbackDeploymentMutation = createMutationAction(
  async (payload: { deployment: Deployment; expectedCurrentVersionId: number; rollbackVersionId: number; reason: string }, context) =>
    consoleClient.rollbackDeployment(payload.deployment.id, {
      expected_current_version_id: payload.expectedCurrentVersionId,
      rollback_agent_version_id: payload.rollbackVersionId,
      rollback_reason: payload.reason,
    }, context),
  { reload: loadRuntimeEntry },
);
const createTaskMutation = createMutationAction(
  async (payload: { deployment: Deployment; input: Record<string, unknown>; threadId?: string }, context) =>
    consoleClient.createDeploymentTask(payload.deployment.id, {
      input: payload.input,
      thread_id: payload.threadId || undefined,
    }, context),
);

async function loadRuntimeEntry() {
  pageError.value = null;
  const runtime = await runtimeQuery.reload();
  if (!runtime) return;
  agents.value = runtime.agents;
  deployments.value = runtime.deployments;
  if (!selectedDeployment.value && deployments.value[0]) {
    selectDeployment(
      deployments.value.find((item) => item.id === Number(props.initialDeploymentId)) ?? deployments.value[0],
    );
  } else if (selectedDeployment.value) {
    selectedDeployment.value = deployments.value.find((item) => item.id === selectedDeployment.value?.id) ?? deployments.value[0] ?? null;
  }
  if (selectedDeployment.value && route.query.tab === "promotion") {
    await openPromotionTab();
  }
  if (!deploymentForm.agentId && agents.value[0]) {
    deploymentForm.agentId = agents.value[0].id;
    await loadVersionsForSelectedAgent();
  }
}

function selectDeploymentRow(row: Record<string, unknown>) {
  selectDeployment(row as Deployment);
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
  taskInputError.value = null;
  resetPromotionState();
}

async function loadVersionsForSelectedAgent() {
  if (!deploymentForm.agentId) {
    versions.value = [];
    deploymentForm.agentVersionId = null;
    return;
  }
  pageError.value = null;
  try {
    versions.value = (await consoleClient.listAgentVersions(deploymentForm.agentId)).items;
    deploymentForm.agentVersionId = versions.value[0]?.id ?? null;
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

async function createDeployment() {
  if (!canCreateDeployment.value || !deploymentForm.agentId || !deploymentForm.agentVersionId) return;
  pageError.value = null;
  try {
    const deployment = await createDeploymentMutation.run(undefined, { auditReason: "create deployment from console" });
    selectDeployment(deployment);
    createOpen.value = false;
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

async function openEditDeployment(deployment: Deployment) {
  editError.value = "";
  pageError.value = null;
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
    pageError.value = toConsoleApiError(caught);
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
  pageError.value = null;
  try {
    const updated = await updateDeploymentMutation.run({
      id: editDeploymentForm.id,
      agentVersionId: editDeploymentForm.agentVersionId,
      environment: editDeploymentForm.environment,
      replicas: editDeploymentForm.replicas,
      config,
    }, { auditReason: "update deployment from console" });
    selectedDeployment.value = updated;
    closeEditDeployment();
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

function parseConfigInput(): Record<string, unknown> | null {
  editError.value = "";
  editConfigError.value = null;
  const parsed = parseJsonObject(editDeploymentForm.configJson);
  if (isJsonParseFailure(parsed)) {
    editConfigError.value = parsed;
    editError.value = parsed.message;
    return null;
  }
  const validationErrors = validateDeploymentConfig({
    environment: editDeploymentForm.environment,
    replicas: editDeploymentForm.replicas,
    config: parsed,
  });
  if (validationErrors.length > 0) {
    editError.value = validationErrors.map((item) => item.message).join(" ");
    return null;
  }
  return parsed;
}

function openArchiveDeployment(deployment: Deployment) {
  archiveTarget.value = deployment;
  archiveDeploymentMutation.error.value = null;
}

function closeArchiveDeployment() {
  if (archivingDeployment.value) return;
  archiveTarget.value = null;
  archiveDeploymentMutation.error.value = null;
}

async function archiveDeployment() {
  if (!archiveTarget.value) return;
  archiveDeploymentMutation.error.value = null;
  try {
    const archived = await archiveDeploymentMutation.run(archiveTarget.value, { auditReason: "archive deployment from console" });
    if (selectedDeployment.value?.id === archived.id && deployments.value[0]) {
      selectedDeployment.value = deployments.value[0];
    }
    archiveTarget.value = null;
  } catch {
    // Error state is owned by archiveDeploymentMutation.
  }
}

async function submitDeploymentTask() {
  if (!selectedDeployment.value) return;
  const input = parseTaskInput();
  if (!input) return;
  pageError.value = null;
  try {
    taskResult.value = await createTaskMutation.run({
      deployment: selectedDeployment.value,
      input,
      threadId: deploymentTaskThreadId.value || undefined,
    }, { auditReason: "submit deployment task from console" });
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

function resetPromotionState() {
  promotionVersions.value = [];
  promotionCandidateVersionId.value = null;
  promotionExperimentRunId.value = null;
  promotionPreview.value = null;
  rolloutReason.value = "";
  rollbackReason.value = "";
  promotionMessage.value = "";
}

async function openPromotionTab() {
  activeDetailTab.value = "promotion";
  promotionMessage.value = "";
  await loadPromotionVersions();
}

async function loadPromotionVersions() {
  if (!selectedDeployment.value) return;
  pageError.value = null;
  try {
    promotionVersions.value = (await consoleClient.listAgentVersions(Number(selectedDeployment.value.agent))).items;
    const currentVersionId = Number(selectedDeployment.value.version);
    promotionCandidateVersionId.value = promotionVersions.value.find((item) => item.id !== currentVersionId)?.id ?? promotionVersions.value[0]?.id ?? null;
    promotionExperimentRunId.value = 401;
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
    promotionVersions.value = [];
    promotionCandidateVersionId.value = null;
    promotionExperimentRunId.value = null;
  }
}

async function previewPromotion() {
  if (!selectedDeployment.value || !promotionCandidateVersionId.value || !promotionExperimentRunId.value) return;
  pageError.value = null;
  promotionMessage.value = "";
  try {
    promotionPreview.value = await promotionPreviewMutation.run({
      deployment: selectedDeployment.value,
      candidateVersionId: promotionCandidateVersionId.value,
      experimentRunId: promotionExperimentRunId.value,
    });
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

async function promoteDeployment() {
  if (!selectedDeployment.value || !promotionCandidateVersionId.value || !promotionExperimentRunId.value || !promotionPreview.value) return;
  pageError.value = null;
  try {
    const previousVersion = promotionPreview.value.currentAgentVersionId;
    const promoted = await promoteDeploymentMutation.run({
      deployment: selectedDeployment.value,
      candidateVersionId: promotionCandidateVersionId.value,
      expectedCurrentVersionId: previousVersion,
      experimentRunId: promotionExperimentRunId.value,
      reason: rolloutReason.value.trim(),
    }, { auditReason: rolloutReason.value.trim() });
    selectedDeployment.value = promoted;
    promotionMessage.value = `${t("promotedToVersion")} ${promoted.version}`;
    promotionPreview.value = {
      ...promotionPreview.value,
      currentAgentVersionId: previousVersion,
      candidateAgentVersionId: Number(promoted.version),
      rollbackAgentVersionId: previousVersion,
    };
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

async function rollbackDeployment() {
  if (!selectedDeployment.value || !promotionPreview.value?.rollbackAgentVersionId) return;
  pageError.value = null;
  try {
    const rolledBack = await rollbackDeploymentMutation.run({
      deployment: selectedDeployment.value,
      expectedCurrentVersionId: Number(selectedDeployment.value.version),
      rollbackVersionId: promotionPreview.value.rollbackAgentVersionId,
      reason: rollbackReason.value.trim(),
    }, { auditReason: rollbackReason.value.trim() });
    selectedDeployment.value = rolledBack;
    promotionMessage.value = `${t("rolledBackToVersion")} ${rolledBack.version}`;
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  }
}

function parseTaskInput(): Record<string, unknown> | null {
  taskInputError.value = null;
  const parsed = parseJsonObject(deploymentTaskInputJson.value);
  if (isJsonParseFailure(parsed)) {
    taskInputError.value = parsed;
    return null;
  }
  return parsed;
}

function openDialog(nextOperation: string, deployment: Deployment) {
  operation.value = nextOperation;
  selected.value = deployment;
  dialogOpen.value = true;
}

async function confirmOperation() {
  if (!selected.value) return;
  pendingOperation.value = selected.value.id;
  pageError.value = null;
  try {
    const updated = await controlDeploymentMutation.run({
      deployment: selected.value,
      operation: operation.value,
    }, { auditReason: `${operation.value} deployment from console` });
    selectedDeployment.value = updated;
  } catch (caught) {
    pageError.value = toConsoleApiError(caught);
  } finally {
    pendingOperation.value = null;
  }
  dialogOpen.value = false;
}

onMounted(loadRuntimeEntry);
</script>

<style scoped>
.dense-loading {
  display: grid;
  gap: 16px;
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

.drawer-form {
  display: grid;
  align-content: start;
  gap: 14px;
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

}
</style>
