<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("agentVersionDeployment") }}</p>
        <h1 class="page-title">{{ t("agents") }}</h1>
        <p class="page-subtitle">{{ t("agentBoundary") }}</p>
      </div>
      <button class="button primary" type="button" :disabled="mode === 'offline' || creating" @click="openCreateAgentDrawer">
        {{ t("registerAgent") }}
      </button>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && agents.length === 0" />

    <section v-if="mode !== 'offline' && loading" class="dense-loading">
      <SkeletonBlock variant="table" :lines="7" />
      <SkeletonBlock :lines="6" />
    </section>

    <DataTable
      v-if="mode !== 'offline' && !loading && !error && agents.length > 0"
      class="agents-table"
      :columns="agentColumns"
      :rows="agents"
      row-key="id"
      :selected-key="selectedAgent?.id ?? null"
      :label="t('agents')"
      selectable
      @row-select="selectAgentRow"
    >
      <template #cell-agent="{ row }">
        <strong>{{ row.name }}</strong><br /><span class="mono muted">{{ row.id }}</span>
      </template>
      <template #cell-description="{ row }">
        {{ row.description || "-" }}
      </template>
      <template #cell-status="{ row }">
        <StatusBadge :status="row.status" :label="row.status" />
      </template>
      <template #cell-createdAt="{ row }">
        {{ formatDateTime(row.createdAt) }}
      </template>
      <template #cell-actions="{ row }">
        <div class="actions-cell">
          <button class="button" type="button" :disabled="pendingAgent === row.id" @click.stop="openEditAgentDrawer(row)">
            {{ t("edit") }}
          </button>
          <button class="button" type="button" :disabled="pendingAgent === row.id" @click.stop="toggleAgentStatus(row)">
            {{ row.status === "disabled" ? t("enable") : t("disable") }}
          </button>
          <button class="button danger" type="button" :disabled="pendingAgent === row.id" @click.stop="openArchiveAgentConfirm(row)">
            {{ t("delete") }}
          </button>
        </div>
      </template>
    </DataTable>

    <section v-if="mode !== 'offline' && !loading && !error && selectedAgent" class="panel agent-detail-panel">
      <div class="panel-header">
        <div>
          <p class="section-kicker">{{ t("logicalAgent") }}</p>
          <h2 class="panel-title">{{ selectedAgent.name }}</h2>
          <p class="muted">{{ t("versionBelongsToAgent") }}</p>
        </div>
        <div class="detail-actions">
          <button class="button primary" type="button" @click="openVersionForm">
            {{ t("addVersion") }}
          </button>
          <button class="button" type="button" @click="openEditAgentDrawer(selectedAgent)">
            {{ t("edit") }}
          </button>
          <button class="button" type="button" :disabled="pendingAgent === selectedAgent.id" @click="toggleAgentStatus(selectedAgent)">
            {{ selectedAgent.status === "disabled" ? t("enable") : t("disable") }}
          </button>
          <RouterLink class="button" to="/deployments">{{ t("openDeployments") }}</RouterLink>
        </div>
      </div>
      <div class="panel-body agent-detail-layout">
        <aside class="agent-summary">
          <p class="section-kicker">{{ t("agentSummary") }}</p>
          <dl>
            <div>
              <dt>{{ t("id") }}</dt>
              <dd class="mono">{{ selectedAgent.id }}</dd>
            </div>
            <div>
              <dt>{{ t("status") }}</dt>
              <dd><StatusBadge :status="selectedAgent.status" :label="selectedAgent.status" /></dd>
            </div>
            <div>
              <dt>{{ t("description") }}</dt>
              <dd>{{ selectedAgent.description || "-" }}</dd>
            </div>
            <div class="metric-row">
              <div>
                <dt>{{ t("versionCount") }}</dt>
                <dd>{{ selectedAgent.versionCount }}</dd>
              </div>
              <div>
                <dt>{{ t("deploymentCount") }}</dt>
                <dd>{{ selectedAgent.deploymentCount }}</dd>
              </div>
            </div>
            <div>
              <dt>{{ t("createdAt") }}</dt>
              <dd>{{ formatDateTime(selectedAgent.createdAt) }}</dd>
            </div>
          </dl>
        </aside>

        <div class="child-workspace">
          <div class="detail-tabs" role="tablist" :aria-label="t('details')">
            <button
              class="tab-button"
              :class="{ active: activeDetailTab === 'versions' }"
              type="button"
              role="tab"
              :aria-selected="activeDetailTab === 'versions'"
              @click="activeDetailTab = 'versions'"
            >
              {{ t("childVersions") }}
            </button>
            <button
              class="tab-button"
              :class="{ active: activeDetailTab === 'deployment' }"
              type="button"
              role="tab"
              :aria-selected="activeDetailTab === 'deployment'"
              @click="activeDetailTab = 'deployment'"
            >
              {{ t("productionRunEntry") }}
            </button>
          </div>

          <section v-if="activeDetailTab === 'versions'" class="child-panel">
            <header class="child-panel-header">
              <div>
                <p class="section-kicker">{{ t("versionImplementation") }}</p>
                <h3>{{ t("versionInventory") }}</h3>
              </div>
              <button class="button" type="button" @click="toggleVersionForm">
                {{ showVersionForm ? t("hideForm") : t("addVersion") }}
              </button>
            </header>

            <form v-if="showVersionForm" class="nested-form" @submit.prevent="createVersion">
              <p class="form-help wide">{{ t("agentVersionFormHelp") }}</p>
              <div v-if="readyVersionSource" class="validated-ready-banner wide">
                <p class="section-kicker">{{ t("readyVersionSource") }}</p>
                <p class="validated-ready-copy">{{ t("readyVersionSourceCopy") }}</p>
                <dl class="validated-ready-meta">
                  <div>
                    <dt>{{ t("validationToken") }}</dt>
                    <dd class="mono">{{ readyVersionSource.validationToken }}</dd>
                  </div>
                  <div>
                    <dt>{{ t("nextAction") }}</dt>
                    <dd>{{ readyVersionSource.nextAction }}</dd>
                  </div>
                </dl>
                <p v-if="readyVersionSource.warnings.length > 0" class="validated-ready-warning">
                  {{ t("packageWarningsRetained") }} {{ readyVersionSource.warnings.join(" ") }}
                </p>
              </div>
              <div class="form-grid">
                <label>
                  <span class="label-row">
                    <span>{{ t("version") }}</span>
                    <button class="field-help-button" type="button" :title="t('versionFieldHelp')" :aria-label="t('versionFieldHelp')">?</button>
                  </span>
                  <input v-model="versionForm.version" class="input" placeholder="0.1.0" required />
                </label>
                <label>
                  <span class="label-row">
                    <span>{{ t("packageUri") }}</span>
                    <button class="field-help-button" type="button" :title="t('packageUriFieldHelp')" :aria-label="t('packageUriFieldHelp')">?</button>
                  </span>
                  <input
                    v-model="versionForm.package_uri"
                    class="input"
                    :placeholder="t('packageUriPlaceholder')"
                    :disabled="Boolean(readyVersionSource)"
                    required
                  />
                </label>
                <label>
                  <span class="label-row">
                    <span>{{ t("framework") }}</span>
                    <button class="field-help-button" type="button" :title="t('frameworkFieldHelp')" :aria-label="t('frameworkFieldHelp')">?</button>
                  </span>
                  <select v-model="versionForm.framework" class="input" :disabled="Boolean(readyVersionSource)" required @change="syncCreateRuntimeAdapter">
                    <option v-for="runtime in supportedAgentRuntimes" :key="runtime.adapter" :value="runtime.framework">
                      {{ runtime.label }}
                    </option>
                  </select>
                </label>
                <label>
                  <span class="label-row">
                    <span>{{ t("adapter") }}</span>
                    <button class="field-help-button" type="button" :title="t('adapterFieldHelp')" :aria-label="t('adapterFieldHelp')">?</button>
                  </span>
                  <select v-model="versionForm.adapter" class="input" :disabled="Boolean(readyVersionSource)" required @change="syncCreateRuntimeFramework">
                    <option v-for="runtime in supportedAgentRuntimes" :key="runtime.adapter" :value="runtime.adapter">
                      {{ runtime.adapter }}
                    </option>
                  </select>
                </label>
                <label class="wide">
                  <span class="label-row">
                    <span>{{ t("entrypoint") }}</span>
                    <button class="field-help-button" type="button" :title="t('entrypointFieldHelp')" :aria-label="t('entrypointFieldHelp')">?</button>
                  </span>
                  <input
                    v-model="versionForm.entrypoint"
                    class="input"
                    :placeholder="t('entrypointPlaceholder')"
                    :disabled="Boolean(readyVersionSource)"
                    required
                  />
                </label>
              </div>
              <div class="nested-form-actions">
                <button class="button" type="button" :disabled="creatingVersion" @click="closeVersionForm">
                  {{ t("cancel") }}
                </button>
                <button class="button primary" type="submit" :disabled="creatingVersion || !canCreateVersion">
                  {{ creatingVersion ? t("creating") : readyVersionSource ? t("createReadyAgentVersion") : t("createAgentVersion") }}
                </button>
              </div>
            </form>

            <div class="version-list">
              <DataTable
                v-if="versions.length > 0"
                :columns="versionColumns"
                :rows="versions"
                row-key="id"
                :label="t('versionInventory')"
              >
                <template #cell-version="{ row }">
                  <strong>{{ row.version }}</strong><br /><span class="mono muted">{{ row.id }}</span>
                </template>
                <template #cell-packageUri="{ row }">
                  <span class="mono">{{ row.packageUri }}</span>
                </template>
                <template #cell-entrypoint="{ row }">
                  <span class="mono">{{ row.entrypoint }}</span>
                </template>
                <template #cell-status="{ row }">
                  <StatusBadge :status="row.status" :label="row.status" />
                </template>
                <template #cell-actions="{ row }">
                  <div class="actions-cell">
                    <button class="button" type="button" :disabled="pendingVersion === row.id" @click="openEditVersionDrawer(row)">
                      {{ t("edit") }}
                    </button>
                    <button class="button" type="button" :disabled="pendingVersion === row.id" @click="toggleVersionStatus(row)">
                      {{ row.status === "disabled" ? t("enable") : t("disable") }}
                    </button>
                    <button class="button danger" type="button" :disabled="pendingVersion === row.id" @click="openArchiveVersionConfirm(row)">
                      {{ t("delete") }}
                    </button>
                  </div>
                </template>
              </DataTable>
              <p v-else class="empty-child">{{ t("noVersionsYet") }}</p>
            </div>
          </section>

          <section v-else class="child-panel deployment-entry">
            <p class="section-kicker">{{ t("deployment") }}</p>
            <h3>{{ t("productionRunEntry") }}</h3>
            <p class="muted">{{ t("deploymentRequiredCopy") }}</p>
            <RouterLink class="button primary" to="/deployments">{{ t("openDeployments") }}</RouterLink>
          </section>
        </div>
      </div>
    </section>

    <AppDrawer
      :open="showCreateAgent"
      :label="t('registerAgent')"
      :title="t('registerAgent')"
      :kicker="t('agentVersionDeployment')"
      @close="closeCreateAgentDrawer"
    >
      <form class="drawer-form" @submit.prevent="createAgent">
        <label>
          <span>{{ t("name") }}</span>
          <input v-model="agentForm.name" class="input" required autofocus />
        </label>
        <label>
          <span>{{ t("description") }}</span>
          <textarea v-model="agentForm.description" class="textarea" rows="5"></textarea>
        </label>
        <div class="drawer-actions">
          <button class="button" type="button" @click="closeCreateAgentDrawer">{{ t("cancel") }}</button>
          <button class="button primary" type="submit" :disabled="creating || !agentForm.name.trim()">
            {{ creating ? t("creating") : t("registerAgent") }}
          </button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer
      :open="showEditAgent && Boolean(editAgentTarget)"
      :label="t('editAgent')"
      :title="t('editAgent')"
      :kicker="editAgentTarget ? `${t('logicalAgent')} #${editAgentTarget.id}` : t('logicalAgent')"
      @close="closeEditAgentDrawer"
    >
      <form class="drawer-form" @submit.prevent="updateAgent">
        <label>
          <span>{{ t("name") }}</span>
          <input v-model="editAgentForm.name" class="input" required autofocus />
        </label>
        <label>
          <span>{{ t("description") }}</span>
          <textarea v-model="editAgentForm.description" class="textarea" rows="6"></textarea>
        </label>
        <div class="drawer-actions">
          <button class="button" type="button" @click="closeEditAgentDrawer">{{ t("cancel") }}</button>
          <button class="button primary" type="submit" :disabled="updatingAgent || !editAgentForm.name.trim()">
            {{ updatingAgent ? t("saving") : t("save") }}
          </button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer
      :open="showEditVersion && Boolean(editVersionTarget)"
      :label="t('editAgentVersion')"
      :title="t('editAgentVersion')"
      :kicker="editVersionTarget ? `${t('versionImplementation')} #${editVersionTarget.id}` : t('versionImplementation')"
      @close="closeEditVersionDrawer"
    >
      <form class="drawer-form" @submit.prevent="updateVersion">
            <p class="form-help">{{ t("agentVersionFormHelp") }}</p>
            <div class="form-grid">
              <label>
                <span class="label-row">
                  <span>{{ t("version") }}</span>
                  <button class="field-help-button" type="button" :title="t('versionFieldHelp')" :aria-label="t('versionFieldHelp')">?</button>
                </span>
                <input v-model="editVersionForm.version" class="input" placeholder="0.1.0" required autofocus />
              </label>
              <label>
                <span>{{ t("status") }}</span>
                <input v-model="editVersionForm.status" class="input" required />
              </label>
              <label class="wide">
                <span class="label-row">
                  <span>{{ t("packageUri") }}</span>
                  <button class="field-help-button" type="button" :title="t('packageUriFieldHelp')" :aria-label="t('packageUriFieldHelp')">?</button>
                </span>
                <input v-model="editVersionForm.package_uri" class="input" :placeholder="t('packageUriPlaceholder')" required />
              </label>
              <label>
                <span class="label-row">
                  <span>{{ t("framework") }}</span>
                  <button class="field-help-button" type="button" :title="t('frameworkFieldHelp')" :aria-label="t('frameworkFieldHelp')">?</button>
                </span>
                <select v-model="editVersionForm.framework" class="input" required @change="syncEditRuntimeAdapter">
                  <option v-for="runtime in supportedAgentRuntimes" :key="runtime.adapter" :value="runtime.framework">
                    {{ runtime.label }}
                  </option>
                </select>
              </label>
              <label>
                <span class="label-row">
                  <span>{{ t("adapter") }}</span>
                  <button class="field-help-button" type="button" :title="t('adapterFieldHelp')" :aria-label="t('adapterFieldHelp')">?</button>
                </span>
                <select v-model="editVersionForm.adapter" class="input" required @change="syncEditRuntimeFramework">
                  <option v-for="runtime in supportedAgentRuntimes" :key="runtime.adapter" :value="runtime.adapter">
                    {{ runtime.adapter }}
                  </option>
                </select>
              </label>
              <label class="wide">
                <span class="label-row">
                  <span>{{ t("entrypoint") }}</span>
                  <button class="field-help-button" type="button" :title="t('entrypointFieldHelp')" :aria-label="t('entrypointFieldHelp')">?</button>
                </span>
                <input v-model="editVersionForm.entrypoint" class="input" :placeholder="t('entrypointPlaceholder')" required />
              </label>
              <label class="wide">
                <span>{{ t("capabilitiesJson") }}</span>
                <textarea v-model="editVersionForm.capabilitiesJson" class="textarea code-textarea" rows="5" required></textarea>
              </label>
              <label class="wide">
                <span>{{ t("manifestJson") }}</span>
                <textarea v-model="editVersionForm.manifestJson" class="textarea code-textarea" rows="6" required></textarea>
              </label>
            </div>
            <div class="drawer-actions">
              <button class="button" type="button" @click="closeEditVersionDrawer">{{ t("cancel") }}</button>
              <button class="button primary" type="submit" :disabled="updatingVersion || !canUpdateVersion">
                {{ updatingVersion ? t("saving") : t("save") }}
              </button>
            </div>
      </form>
    </AppDrawer>

    <DangerConfirmDialog
      :open="Boolean(archiveAgentTarget)"
      :title="t('deleteAgent')"
      :message="t('deleteAgentCopy')"
      :items="archiveAgentConfirmItems"
      :confirm-label="t('delete')"
      :cancel-label="t('cancel')"
      :busy-label="t('saving')"
      :busy="Boolean(archiveAgentTarget && pendingAgent === archiveAgentTarget.id)"
      :error="archiveAgentError"
      @cancel="closeArchiveAgentConfirm"
      @confirm="runConfirmedArchiveAgent"
    />

    <DangerConfirmDialog
      :open="Boolean(archiveVersionTarget)"
      :title="t('deleteAgentVersion')"
      :message="t('deleteAgentVersionCopy')"
      :items="archiveVersionConfirmItems"
      :confirm-label="t('delete')"
      :cancel-label="t('cancel')"
      :busy-label="t('saving')"
      :busy="Boolean(archiveVersionTarget && pendingVersion === archiveVersionTarget.id)"
      :error="archiveVersionError"
      @cancel="closeArchiveVersionConfirm"
      @confirm="runConfirmedArchiveVersion"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { apiMode, consoleClient, toConsoleApiError, type ConsoleApiError } from "../../api/client";
import type { Agent, AgentVersion } from "../../api/types";
import ApiState from "../../components/ApiState.vue";
import AppDrawer from "../../components/AppDrawer.vue";
import DataTable from "../../components/DataTable.vue";
import DangerConfirmDialog from "../../components/DangerConfirmDialog.vue";
import SkeletonBlock from "../../components/SkeletonBlock.vue";
import StatusBadge from "../../components/StatusBadge.vue";
import { useI18n } from "../../i18n/useI18n";
import { formatDateTime } from "../../utils/dateTime";
import {
  clearReadyVersionDraft,
  readReadyVersionDraft,
  type ReadyVersionDraft,
} from "../../workflows/packageValidationDraft";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const mode = apiMode();
const loading = ref(false);
const creating = ref(false);
const updatingAgent = ref(false);
const updatingVersion = ref(false);
const creatingVersion = ref(false);
const showCreateAgent = ref(false);
const showEditAgent = ref(false);
const showEditVersion = ref(false);
const showVersionForm = ref(false);
const error = ref<ConsoleApiError | null>(null);
const archiveAgentError = ref<ConsoleApiError | null>(null);
const archiveVersionError = ref<ConsoleApiError | null>(null);
const pendingAgent = ref<number | null>(null);
const pendingVersion = ref<number | null>(null);
const agents = ref<Agent[]>([]);
const selectedAgent = ref<Agent | null>(null);
const editAgentTarget = ref<Agent | null>(null);
const archiveAgentTarget = ref<Agent | null>(null);
const editVersionTarget = ref<AgentVersion | null>(null);
const archiveVersionTarget = ref<AgentVersion | null>(null);
const versions = ref<AgentVersion[]>([]);
const readyVersionSource = ref<ReadyVersionDraft | null>(readReadyVersionDraft());
const readyVersionSourceHandled = ref(false);
const activeDetailTab = ref<"versions" | "deployment">("versions");
const supportedAgentRuntimes = [
  { label: "LangGraph", framework: "langgraph", adapter: "langgraph" },
  { label: "LangChain Agent", framework: "langchain-agent", adapter: "langchain-agent" },
  { label: "Deep Agents", framework: "deepagents", adapter: "deepagents" },
] as const;
const agentForm = reactive({
  name: "",
  description: "",
});
const editAgentForm = reactive({
  name: "",
  description: "",
});
const versionForm = reactive({
  version: "",
  package_uri: "",
  framework: "",
  adapter: "",
  entrypoint: "",
});
const editVersionForm = reactive({
  version: "",
  package_uri: "",
  framework: "",
  adapter: "",
  entrypoint: "",
  capabilitiesJson: "{}",
  manifestJson: "{}",
  status: "ready",
});
const canCreateVersion = computed(() =>
  Boolean(
    versionForm.version.trim()
    && versionForm.package_uri.trim()
    && versionForm.framework.trim()
    && versionForm.adapter.trim()
    && versionForm.entrypoint.trim(),
  ),
);
const archiveAgentConfirmItems = computed(() => archiveAgentTarget.value ? [
  { label: t("agent"), value: archiveAgentTarget.value.name },
  { label: t("id"), value: String(archiveAgentTarget.value.id) },
  { label: t("status"), value: archiveAgentTarget.value.status },
] : []);
const canUpdateVersion = computed(() =>
  Boolean(
    editVersionForm.version.trim()
    && editVersionForm.package_uri.trim()
    && editVersionForm.framework.trim()
    && editVersionForm.adapter.trim()
    && editVersionForm.entrypoint.trim()
    && editVersionForm.status.trim(),
  ),
);
const archiveVersionConfirmItems = computed(() => archiveVersionTarget.value ? [
  { label: t("version"), value: archiveVersionTarget.value.version },
  { label: t("id"), value: String(archiveVersionTarget.value.id) },
  { label: t("status"), value: archiveVersionTarget.value.status },
] : []);
const agentColumns = computed(() => [
  { key: "agent", label: t("agent") },
  { key: "description", label: t("description") },
  { key: "status", label: t("status") },
  { key: "versionCount", label: t("versionCount"), align: "center" as const },
  { key: "deploymentCount", label: t("deploymentCount"), align: "center" as const },
  { key: "createdAt", label: t("createdAt") },
  { key: "actions", label: t("actions") },
]);
const versionColumns = computed(() => [
  { key: "version", label: t("version") },
  { key: "packageUri", label: t("packageUri") },
  { key: "framework", label: t("framework") },
  { key: "adapter", label: t("adapter") },
  { key: "entrypoint", label: t("entrypoint") },
  { key: "status", label: t("status") },
  { key: "actions", label: t("actions") },
]);

async function loadAgents() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    agents.value = (await consoleClient.listAgents()).items;
    if (!selectedAgent.value && agents.value[0]) {
      await selectAgent(agents.value[0]);
    } else if (readyVersionSource.value && agents.value.length === 0) {
      openCreateAgentDrawer();
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

function selectAgentRow(row: Record<string, unknown>) {
  void selectAgent(row as Agent);
}

function openCreateAgentDrawer() {
  agentForm.name = "";
  agentForm.description = "";
  showCreateAgent.value = true;
}

function closeCreateAgentDrawer() {
  if (creating.value) return;
  showCreateAgent.value = false;
  agentForm.name = "";
  agentForm.description = "";
}

async function createAgent() {
  const name = agentForm.name.trim();
  if (!name) return;
  creating.value = true;
  error.value = null;
  try {
    const agent = await consoleClient.createAgent({
      name,
      description: agentForm.description.trim() || null,
    });
    agents.value = [agent, ...agents.value];
    await selectAgent(agent);
    showCreateAgent.value = false;
    agentForm.name = "";
    agentForm.description = "";
    maybeOpenReadyVersionWorkflow();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creating.value = false;
  }
}

function openEditAgentDrawer(agent: Agent) {
  editAgentTarget.value = agent;
  editAgentForm.name = agent.name;
  editAgentForm.description = agent.description || "";
  showEditAgent.value = true;
}

function closeEditAgentDrawer() {
  if (updatingAgent.value) return;
  showEditAgent.value = false;
  editAgentTarget.value = null;
  editAgentForm.name = "";
  editAgentForm.description = "";
}

async function updateAgent() {
  if (!editAgentTarget.value || !editAgentForm.name.trim()) return;
  updatingAgent.value = true;
  error.value = null;
  try {
    const counts = {
      versionCount: editAgentTarget.value.versionCount,
      deploymentCount: editAgentTarget.value.deploymentCount,
    };
    const agent = {
      ...(await consoleClient.updateAgent(editAgentTarget.value.id, {
        name: editAgentForm.name.trim(),
        description: editAgentForm.description.trim() || null,
      })),
      ...counts,
    };
    agents.value = agents.value.map((item) => (item.id === agent.id ? agent : item));
    if (selectedAgent.value?.id === agent.id) {
      selectedAgent.value = agent;
    }
    closeEditAgentDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    updatingAgent.value = false;
  }
}

async function toggleAgentStatus(agent: Agent) {
  pendingAgent.value = agent.id;
  error.value = null;
  try {
    const updated = {
      ...(await consoleClient.updateAgent(agent.id, {
        name: agent.name,
        description: agent.description,
        status: agent.status === "disabled" ? "active" : "disabled",
      })),
      versionCount: agent.versionCount,
      deploymentCount: agent.deploymentCount,
    };
    agents.value = agents.value.map((item) => (item.id === updated.id ? updated : item));
    if (selectedAgent.value?.id === updated.id) {
      selectedAgent.value = updated;
    }
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingAgent.value = null;
  }
}

function openArchiveAgentConfirm(agent: Agent) {
  archiveAgentTarget.value = agent;
  archiveAgentError.value = null;
}

function closeArchiveAgentConfirm() {
  if (archiveAgentTarget.value && pendingAgent.value === archiveAgentTarget.value.id) return;
  archiveAgentTarget.value = null;
  archiveAgentError.value = null;
}

async function runConfirmedArchiveAgent() {
  if (!archiveAgentTarget.value) return;
  pendingAgent.value = archiveAgentTarget.value.id;
  error.value = null;
  archiveAgentError.value = null;
  try {
    const agent = await consoleClient.archiveAgent(archiveAgentTarget.value.id);
    agents.value = agents.value.filter((item) => item.id !== agent.id);
    if (selectedAgent.value?.id === agent.id) {
      selectedAgent.value = agents.value[0] ?? null;
      versions.value = [];
      if (selectedAgent.value) {
        await selectAgent(selectedAgent.value);
      }
    }
    archiveAgentTarget.value = null;
  } catch (caught) {
    archiveAgentError.value = toConsoleApiError(caught);
  } finally {
    pendingAgent.value = null;
  }
}

async function selectAgent(agent: Agent) {
  selectedAgent.value = agent;
  activeDetailTab.value = "versions";
  showVersionForm.value = false;
  error.value = null;
  try {
    versions.value = (await consoleClient.listAgentVersions(agent.id)).items;
    maybeOpenReadyVersionWorkflow();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  }
}

function resetVersionForm() {
  versionForm.version = "";
  if (readyVersionSource.value) {
    applyReadyVersionSource();
    return;
  }
  versionForm.package_uri = "";
  versionForm.framework = supportedAgentRuntimes[0].framework;
  versionForm.adapter = supportedAgentRuntimes[0].adapter;
  versionForm.entrypoint = "";
}

function openVersionForm() {
  activeDetailTab.value = "versions";
  if (readyVersionSource.value) {
    applyReadyVersionSource();
  } else if (!versionForm.framework || !versionForm.adapter) {
    syncCreateRuntimeAdapter();
  }
  showVersionForm.value = true;
}

function toggleVersionForm() {
  if (showVersionForm.value) {
    showVersionForm.value = false;
    return;
  }
  openVersionForm();
}

function closeVersionForm() {
  if (creatingVersion.value) return;
  showVersionForm.value = false;
  resetVersionForm();
}

function runtimeForFramework(framework: string) {
  return supportedAgentRuntimes.find((runtime) => runtime.framework === framework);
}

function runtimeForAdapter(adapter: string) {
  return supportedAgentRuntimes.find((runtime) => runtime.adapter === adapter);
}

function syncCreateRuntimeAdapter() {
  const runtime = runtimeForFramework(versionForm.framework) ?? supportedAgentRuntimes[0];
  versionForm.framework = runtime.framework;
  versionForm.adapter = runtime.adapter;
}

function syncCreateRuntimeFramework() {
  const runtime = runtimeForAdapter(versionForm.adapter) ?? supportedAgentRuntimes[0];
  versionForm.framework = runtime.framework;
  versionForm.adapter = runtime.adapter;
}

function syncEditRuntimeAdapter() {
  const runtime = runtimeForFramework(editVersionForm.framework) ?? supportedAgentRuntimes[0];
  editVersionForm.framework = runtime.framework;
  editVersionForm.adapter = runtime.adapter;
}

function syncEditRuntimeFramework() {
  const runtime = runtimeForAdapter(editVersionForm.adapter) ?? supportedAgentRuntimes[0];
  editVersionForm.framework = runtime.framework;
  editVersionForm.adapter = runtime.adapter;
}

async function createVersion() {
  if (!selectedAgent.value || !canCreateVersion.value) return;
  creatingVersion.value = true;
  error.value = null;
  try {
    const payload = readyVersionSource.value
      ? {
        ...versionForm,
        capabilities: readyVersionSource.value.capabilities,
        manifest: {
          ...readyVersionSource.value.manifest,
          validation_token: readyVersionSource.value.validationToken,
        },
        status: "ready",
      }
      : {
        ...versionForm,
        capabilities: { invoke: true, stream: true },
        manifest: {
          runtime: {
            framework: versionForm.framework,
            adapter: versionForm.adapter,
            entrypoint: versionForm.entrypoint,
          },
        },
        status: "draft",
      };
    const version = await consoleClient.createAgentVersion(selectedAgent.value.id, {
      ...payload,
    });
    versions.value = [version, ...versions.value.filter((item) => item.id !== version.id)];
    agents.value = agents.value.map((agent) => agent.id === selectedAgent.value?.id
      ? { ...agent, versionCount: versions.value.length }
      : agent);
    if (selectedAgent.value) {
      selectedAgent.value = { ...selectedAgent.value, versionCount: versions.value.length };
    }
    showVersionForm.value = false;
    if (readyVersionSource.value) {
      clearReadyVersionDraft();
      readyVersionSource.value = null;
      readyVersionSourceHandled.value = true;
      if (route.query.workflow) {
        void router.replace({ path: route.path, query: {} });
      }
    }
    resetVersionForm();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    creatingVersion.value = false;
  }
}

function openEditVersionDrawer(version: AgentVersion) {
  editVersionTarget.value = version;
  editVersionForm.version = version.version;
  editVersionForm.package_uri = version.packageUri;
  editVersionForm.framework = version.framework;
  editVersionForm.adapter = version.adapter;
  editVersionForm.entrypoint = version.entrypoint;
  editVersionForm.capabilitiesJson = JSON.stringify(version.capabilities || {}, null, 2);
  editVersionForm.manifestJson = JSON.stringify(version.manifest || {}, null, 2);
  editVersionForm.status = version.status;
  showEditVersion.value = true;
}

function closeEditVersionDrawer() {
  if (updatingVersion.value) return;
  showEditVersion.value = false;
  editVersionTarget.value = null;
  editVersionForm.version = "";
  editVersionForm.package_uri = "";
  editVersionForm.framework = "";
  editVersionForm.adapter = "";
  editVersionForm.entrypoint = "";
  editVersionForm.capabilitiesJson = "{}";
  editVersionForm.manifestJson = "{}";
  editVersionForm.status = "ready";
}

function parseJsonObject(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(t("jsonObjectRequired"));
  }
  return parsed as Record<string, unknown>;
}

async function updateVersion() {
  if (!selectedAgent.value || !editVersionTarget.value || !canUpdateVersion.value) return;
  updatingVersion.value = true;
  error.value = null;
  try {
    const capabilities = parseJsonObject(editVersionForm.capabilitiesJson);
    const manifest = parseJsonObject(editVersionForm.manifestJson);
    const updated = await consoleClient.updateAgentVersion(
      selectedAgent.value.id,
      editVersionTarget.value.version,
      {
        version: editVersionForm.version.trim(),
        package_uri: editVersionForm.package_uri.trim(),
        framework: editVersionForm.framework.trim(),
        adapter: editVersionForm.adapter.trim(),
        entrypoint: editVersionForm.entrypoint.trim(),
        capabilities,
        manifest,
        status: editVersionForm.status.trim(),
      },
    );
    versions.value = versions.value.map((item) => (item.id === updated.id ? updated : item));
    closeEditVersionDrawer();
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    updatingVersion.value = false;
  }
}

async function toggleVersionStatus(version: AgentVersion) {
  if (!selectedAgent.value) return;
  pendingVersion.value = version.id;
  error.value = null;
  try {
    const updated = await consoleClient.updateAgentVersion(
      selectedAgent.value.id,
      version.version,
      {
        version: version.version,
        package_uri: version.packageUri,
        framework: version.framework,
        adapter: version.adapter,
        entrypoint: version.entrypoint,
        capabilities: version.capabilities,
        manifest: version.manifest,
        status: version.status === "disabled" ? "ready" : "disabled",
      },
    );
    versions.value = versions.value.map((item) => (item.id === updated.id ? updated : item));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    pendingVersion.value = null;
  }
}

function openArchiveVersionConfirm(version: AgentVersion) {
  archiveVersionTarget.value = version;
  archiveVersionError.value = null;
}

function closeArchiveVersionConfirm() {
  if (archiveVersionTarget.value && pendingVersion.value === archiveVersionTarget.value.id) return;
  archiveVersionTarget.value = null;
  archiveVersionError.value = null;
}

async function runConfirmedArchiveVersion() {
  if (!selectedAgent.value || !archiveVersionTarget.value) return;
  pendingVersion.value = archiveVersionTarget.value.id;
  error.value = null;
  archiveVersionError.value = null;
  try {
    const archived = await consoleClient.archiveAgentVersion(
      selectedAgent.value.id,
      archiveVersionTarget.value.version,
    );
    versions.value = versions.value.filter((item) => item.id !== archived.id);
    agents.value = agents.value.map((agent) => agent.id === selectedAgent.value?.id
      ? { ...agent, versionCount: versions.value.length }
      : agent);
    selectedAgent.value = { ...selectedAgent.value, versionCount: versions.value.length };
    archiveVersionTarget.value = null;
  } catch (caught) {
    archiveVersionError.value = toConsoleApiError(caught);
  } finally {
    pendingVersion.value = null;
  }
}

function maybeOpenReadyVersionWorkflow() {
  if (!readyVersionSource.value || readyVersionSourceHandled.value || !selectedAgent.value) return;
  if (route.query.workflow !== "package-validation") return;
  openVersionForm();
  readyVersionSourceHandled.value = true;
}

function applyReadyVersionSource() {
  if (!readyVersionSource.value) return;
  versionForm.package_uri = readyVersionSource.value.packageUri;
  versionForm.framework = readyVersionSource.value.framework;
  versionForm.adapter = readyVersionSource.value.adapter;
  versionForm.entrypoint = readyVersionSource.value.entrypoint;
  if (!versionForm.version.trim()) {
    versionForm.version = extractVersionHint(readyVersionSource.value.packageUri);
  }
}

function extractVersionHint(packageUri: string): string {
  const match = packageUri.match(/:([^/:]+)$/);
  if (!match) return "";
  return match[1] === "latest" ? "" : match[1];
}

onMounted(loadAgents);
</script>

<style scoped>
.actions-cell {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dense-loading {
  display: grid;
  gap: 16px;
}

.agent-detail-panel {
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

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.agent-detail-layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 16px;
}

.agent-summary {
  display: grid;
  align-content: start;
  border-right: 1px solid var(--color-border);
  gap: 10px;
  padding-right: 16px;
}

.agent-summary dl {
  display: grid;
  gap: 12px;
  margin: 0;
}

.agent-summary dt {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.agent-summary dd {
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
  gap: 14px;
  margin-top: 14px;
}

.child-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.child-panel-header h3,
.deployment-entry h3 {
  margin: 0;
  font-size: 1rem;
}

.nested-form {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 14px;
}

.nested-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.validated-ready-banner {
  display: grid;
  gap: 10px;
  border: 1px solid color-mix(in oklab, var(--color-success) 40%, var(--color-border));
  border-radius: 8px;
  background: color-mix(in oklab, var(--color-success) 10%, var(--color-surface));
  padding: 12px;
}

.validated-ready-copy,
.validated-ready-warning {
  margin: 0;
}

.validated-ready-meta {
  display: grid;
  gap: 10px;
  margin: 0;
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

.form-help {
  color: var(--color-text-muted);
  font-weight: 600;
  line-height: 1.45;
}

.label-row {
  align-items: center;
  display: inline-flex;
  gap: 6px;
  justify-self: start;
}

.field-help-button {
  display: inline-grid;
  width: 16px;
  height: 16px;
  place-items: center;
  border: 1px solid color-mix(in oklab, var(--color-text-muted) 45%, var(--color-border));
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-muted);
  cursor: help;
  font: inherit;
  font-size: 0.68rem;
  font-weight: 800;
  line-height: 1;
  padding: 0;
}

.field-help-button:hover,
.field-help-button:focus-visible {
  border-color: var(--color-primary);
  color: var(--color-primary);
  outline: none;
}

.form-help {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  font-size: 0.78rem;
  margin: 0;
  padding: 10px 12px;
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

.code-textarea {
  font-family: var(--font-mono);
  font-size: 0.84rem;
}

.wide {
  grid-column: 1 / -1;
}

.version-list {
  overflow: auto;
}

.empty-child {
  border: 1px dashed var(--color-border);
  border-radius: 8px;
  color: var(--color-text-muted);
  margin: 0;
  padding: 18px;
}

.deployment-entry {
  align-content: start;
  justify-items: start;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface-muted);
  padding: 16px;
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
  .agent-detail-layout,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .agent-summary {
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
    padding-right: 0;
    padding-bottom: 14px;
  }
}
</style>
