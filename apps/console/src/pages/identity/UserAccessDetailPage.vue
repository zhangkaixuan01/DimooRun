<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("identity") }}</p>
        <h1 class="page-title">User Access Detail</h1>
        <p class="page-subtitle">Assigned roles, inherited permissions, active sessions, issued keys, and recent audit facts for one operator.</p>
      </div>
      <div class="header-actions">
        <RouterLink class="button" to="/identity/operators">Back to operators</RouterLink>
        <button
          v-if="isSelf"
          class="button danger"
          type="button"
          :disabled="busy"
          @click="revokeCurrentBrowserSession"
        >
          Revoke current browser session
        </button>
      </div>
    </header>

    <ApiState :mode="mode" :loading="loading" :error="error" :empty="!loading && !detail" />

    <div v-if="mode !== 'offline' && !loading && !error && detail" class="detail-layout">
      <section class="panel hero-panel">
        <div>
          <p class="section-kicker">Operator</p>
          <h2 class="panel-title">{{ detail.item.name }}</h2>
          <p class="muted">{{ detail.item.email }}</p>
        </div>
        <div class="summary-grid">
          <div>
            <span>Status</span>
            <strong>{{ detail.item.status }}</strong>
          </div>
          <div>
            <span>Roles</span>
            <strong>{{ detail.item.roles.join(", ") || "-" }}</strong>
          </div>
          <div>
            <span>Permissions</span>
            <strong>{{ detail.item.permissions.length }}</strong>
          </div>
          <div>
            <span>Active sessions</span>
            <strong>{{ detail.item.disable_impact.active_session_count }}</strong>
          </div>
        </div>
      </section>

      <InlineApiError :error="mutationError" />

      <div class="panel-grid">
        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">Effective access</p>
              <h3 class="panel-title">Roles and permissions</h3>
            </div>
          </header>
          <div class="panel-body chips-wrap">
            <article class="fact-block">
              <strong>Assigned roles</strong>
              <div class="chips">
                <span v-for="role in detail.item.roles" :key="role" class="chip">{{ role }}</span>
              </div>
            </article>
            <article class="fact-block">
              <strong>Inherited permissions</strong>
              <div class="chips">
                <span v-for="permission in detail.item.permissions" :key="permission" class="chip mono">{{ permission }}</span>
              </div>
            </article>
            <article class="fact-block">
              <strong>Disable impact</strong>
              <p class="muted">Revoking this operator blocks {{ detail.item.disable_impact.active_session_count }} active sessions and leaves {{ detail.item.disable_impact.api_keys_created_count }} created API keys as audit evidence.</p>
            </article>
          </div>
        </section>

        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">Sessions</p>
              <h3 class="panel-title">Active sessions</h3>
            </div>
          </header>
          <div class="table-wrap embedded">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Status</th>
                  <th>Last used</th>
                  <th>Expires</th>
                  <th>Client</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="session in detail.item.active_sessions" :key="session.id">
                  <td class="mono">{{ session.id }}</td>
                  <td>{{ session.status }}</td>
                  <td>{{ formatDateTime(session.last_used_at) }}</td>
                  <td>{{ formatDateTime(session.expires_at) }}</td>
                  <td>{{ session.ip_address || "-" }} / {{ session.user_agent || "-" }}</td>
                  <td>
                    <button class="button danger" type="button" :disabled="busy" @click="revokeSession(session.id)">
                      Revoke session
                    </button>
                  </td>
                </tr>
                <tr v-if="detail.item.active_sessions.length === 0">
                  <td colspan="6" class="muted">No active sessions.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">Issued API keys</p>
              <h3 class="panel-title">Keys created by this operator</h3>
            </div>
          </header>
          <div class="table-wrap embedded">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Owner</th>
                  <th>Scopes</th>
                  <th>Status</th>
                  <th>Expires</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="key in detail.item.api_keys_created" :key="key.id">
                  <td><strong>{{ key.name || key.id }}</strong></td>
                  <td class="mono">{{ key.owner_id }}</td>
                  <td>{{ listValue(key.scopes) }}</td>
                  <td>{{ key.status || "-" }}</td>
                  <td>{{ formatDateTime(key.expires_at) }}</td>
                </tr>
                <tr v-if="detail.item.api_keys_created.length === 0">
                  <td colspan="5" class="muted">This operator has not created API keys.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <header class="panel-header">
            <div>
              <p class="section-kicker">Audit</p>
              <h3 class="panel-title">Recent access actions</h3>
            </div>
          </header>
          <div class="audit-list">
            <article v-for="entry in detail.item.recent_audit_actions" :key="entry.id" class="audit-row">
              <strong>{{ entry.action || entry.id }}</strong>
              <span class="mono">{{ entry.resource_type }} / {{ entry.resource_id }}</span>
              <small>{{ formatDateTime(entry.created_at) }}</small>
            </article>
            <p v-if="detail.item.recent_audit_actions.length === 0" class="muted">No recent audit actions.</p>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import {
  apiMode,
  consoleClient,
  toConsoleApiError,
  type ConsoleApiError,
  type OperatorAccessDetail,
} from "../../api/client";
import ApiState from "../../components/ApiState.vue";
import InlineApiError from "../../components/InlineApiError.vue";
import { useI18n } from "../../i18n/useI18n";
import { useAuthStore } from "../../stores/auth";
import { formatDateTime } from "../../utils/dateTime";

const props = defineProps<{ operatorId: string | number }>();

const { t } = useI18n();
const auth = useAuthStore();
const mode = apiMode();
const loading = ref(false);
const busy = ref(false);
const error = ref<ConsoleApiError | null>(null);
const mutationError = ref<ConsoleApiError | null>(null);
const detail = ref<OperatorAccessDetail | null>(null);

const isSelf = computed(() => String(detail.value?.item.id || "") === String(auth.operator?.id || ""));

async function load() {
  if (mode === "offline") return;
  loading.value = true;
  error.value = null;
  try {
    detail.value = await consoleClient.getOperatorAccessDetail(Number(props.operatorId));
  } catch (caught) {
    error.value = toConsoleApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function revokeSession(sessionId: string | number) {
  busy.value = true;
  mutationError.value = null;
  try {
    await consoleClient.revokeOperatorSession(Number(props.operatorId), Number(sessionId));
    await load();
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

async function revokeCurrentBrowserSession() {
  const token = localStorage.getItem("dimoorun.console.token") || "";
  if (!token) return;
  busy.value = true;
  mutationError.value = null;
  try {
    await consoleClient.revokeOwnConsoleSession(token);
    localStorage.removeItem("dimoorun.console.token");
    localStorage.removeItem("dimoorun.console.operator");
    window.location.assign("/login");
  } catch (caught) {
    mutationError.value = toConsoleApiError(caught);
  } finally {
    busy.value = false;
  }
}

function listValue(value: unknown): string {
  return Array.isArray(value) ? value.map(String).join(", ") : "-";
}

onMounted(load);
</script>

<style scoped>
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-layout,
.panel-grid {
  display: grid;
  gap: 14px;
}

.hero-panel,
.panel {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 460px);
  gap: 14px;
  padding: 18px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px;
}

.panel-title {
  margin: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.summary-grid div,
.fact-block,
.audit-row {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 48%, transparent);
  padding: 10px;
}

.summary-grid span,
.muted,
.audit-row small {
  color: var(--color-text-muted);
  font-size: 12px;
}

.summary-grid strong {
  display: block;
  margin-top: 4px;
}

.panel-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel-body,
.audit-list {
  display: grid;
  gap: 12px;
  padding: 14px;
}

.chips-wrap {
  align-content: start;
}

.fact-block {
  display: grid;
  gap: 8px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  font-size: 12px;
}

.embedded {
  border: 0;
  border-radius: 0;
}

.audit-list {
  align-content: start;
}

.audit-row {
  display: grid;
  gap: 4px;
}

@media (max-width: 1000px) {
  .hero-panel,
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
