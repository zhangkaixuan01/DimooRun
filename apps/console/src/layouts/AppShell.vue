<template>
  <div class="shell">
    <aside class="sidebar" :aria-label="t('primaryNav')">
      <RouterLink class="brand" to="/dashboard">
        <span class="brand-mark">D</span>
        <span>
          <strong>DimooRun</strong>
          <small>{{ t("runtimeControlPlane") }}</small>
        </span>
      </RouterLink>

      <nav class="nav">
        <section v-for="group in navGroups" :key="group.label">
          <p>{{ group.label }}</p>
          <RouterLink v-for="item in group.items" :key="item.to" class="nav-item" :to="item.to">
            <span class="nav-glyph" aria-hidden="true">{{ item.icon }}</span>
            {{ item.label }}
          </RouterLink>
        </section>
      </nav>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="context">
          <div v-if="showScopeSelector" class="scope-selectors" :aria-label="t('organizationScope')">
            <label>
              {{ t("tenant") }}
              <select class="select" :value="scope.currentScope.tenant_id" @change="setTenant">
                <option v-for="item in scope.tenantOptions" :key="item.tenant_id" :value="item.tenant_id">
                  {{ scopeLabel(item.tenant_name, item.tenant_id) }}
                </option>
              </select>
            </label>
            <label>
              {{ t("project") }}
              <select class="select" :value="scope.currentScope.project_id" @change="setProject">
                <option v-for="item in scope.projectOptions" :key="item.project_id" :value="item.project_id">
                  {{ scopeLabel(item.project_name, item.project_id) }}
                </option>
              </select>
            </label>
            <label>
              {{ t("environment") }}
              <select class="select" :value="scope.currentScope.environment" @change="setEnvironment">
                <option v-for="item in scope.environmentOptions" :key="item.environment" :value="item.environment">
                  {{ item.environment_name || item.environment }}
                </option>
              </select>
            </label>
          </div>
          <span class="mode-pill" :data-mode="mode">{{ t("apiMode") }}: {{ modeLabel }}</span>
        </div>

        <div class="actions">
          <input class="input search" :placeholder="t('globalSearch')" />
          <button class="button" type="button" @click="preferences.toggleLiveRefresh()">
            {{ preferences.liveRefresh ? t("pauseRefresh") : t("resumeRefresh") }}
          </button>
          <button
            class="button icon-button"
            data-testid="theme-toggle"
            type="button"
            :title="preferences.theme === 'light' ? t('dark') : t('light')"
            @click="toggleTheme"
          >
            {{ preferences.theme === "light" ? t("dark") : t("light") }}
          </button>
          <button
            class="button icon-button"
            data-testid="language-toggle"
            type="button"
            :title="preferences.locale === 'zh-CN' ? t('english') : t('chinese')"
            @click="toggleLocale"
          >
            {{ preferences.locale === "zh-CN" ? "EN" : "中" }}
          </button>
          <span v-if="auth.operator" class="operator-pill">{{ auth.operator.name }}</span>
          <button class="button" type="button" @click="logout">{{ t("logout") }}</button>
        </div>
      </header>

      <main ref="contentRef" class="content">
        <RouterView :key="`${route.fullPath}:${scopeVersion}`" />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { gsap } from "gsap";
import { useRoute } from "vue-router";

import { apiMode } from "../api/client";
import { useI18n } from "../i18n/useI18n";
import { useAuthStore } from "../stores/auth";
import { usePreferencesStore } from "../stores/preferences";
import { useScopeStore } from "../stores/scope";

const preferences = usePreferencesStore();
const auth = useAuthStore();
const scope = useScopeStore();
const { t } = useI18n();
const route = useRoute();
const contentRef = ref<HTMLElement | null>(null);
const scopeVersion = ref(0);
const mode = apiMode();
const modeLabel = computed(() => (mode === "live" ? t("live") : t("offline")));
const showScopeSelector = computed(() => {
  const path = route.path;
  if (path.startsWith("/identity")) return false;
  if (path === "/settings") return false;
  return true;
});
let ctx: gsap.Context | undefined;

preferences.hydrateDocument();
if (auth.operator) scope.initialize(auth.operator.allowed_scopes);

const navGroups = computed(() => [
  {
    label: t("overview"),
    items: [{ label: t("dashboard"), to: "/dashboard", icon: "O" }],
  },
  {
    label: t("runtime"),
    items: [
      { label: t("agents"), to: "/agents", icon: "A" },
      { label: "Packages", to: "/packages/register", icon: "K" },
      { label: t("deployments"), to: "/deployments", icon: "D" },
      { label: t("publishedSurfaces"), to: "/published-surfaces", icon: "P" },
      { label: "Workers", to: "/runtime/workers", icon: "W" },
      { label: "Agent Instances", to: "/runtime/agent-instances", icon: "I" },
      { label: "Capacity", to: "/runtime/capacity", icon: "C" },
      { label: t("runs"), to: "/runs", icon: "R" },
      { label: t("tasks"), to: "/tasks", icon: "T" },
    ],
  },
  {
    label: t("observability"),
    items: [
      { label: t("events"), to: "/events", icon: "E" },
      { label: t("replay"), to: "/replay", icon: "B" },
      { label: t("auditLogs"), to: "/observability/audit-logs", icon: "L" },
      { label: t("artifacts"), to: "/observability/artifacts", icon: "F" },
      { label: t("datasets"), to: "/observability/datasets", icon: "D" },
      { label: t("experiments"), to: "/observability/experiments", icon: "X" },
      { label: t("qualityGate"), to: "/observability/quality-gate", icon: "G" },
      { label: t("evaluationResults"), to: "/observability/evaluations", icon: "V" },
      { label: t("feedback"), to: "/observability/feedback", icon: "Q" },
      { label: t("replayJobs"), to: "/observability/replay-jobs", icon: "J" },
    ],
  },
  {
    label: t("identity"),
    items: [
      { label: t("organizationScope"), to: "/identity/scopes", icon: "S" },
      { label: t("operators"), to: "/identity/operators", icon: "O" },
      { label: t("rolesPermissions"), to: "/identity/roles-permissions", icon: "R" },
      { label: t("machineIdentity"), to: "/identity/machine-identities", icon: "M" },
    ],
  },
  {
    label: t("governance"),
    items: [
      { label: t("humanTasks"), to: "/governance/human-tasks", icon: "H" },
      { label: t("policies"), to: "/governance/policies", icon: "G" },
      { label: t("modelGateways"), to: "/governance/model-gateways", icon: "M" },
      { label: t("tools"), to: "/governance/tools", icon: "T" },
      { label: t("secrets"), to: "/governance/secrets", icon: "S" },
      { label: t("catalogItems"), to: "/governance/catalog-items", icon: "C" },
      { label: t("promptAssets"), to: "/governance/prompt-assets", icon: "P" },
      { label: t("configAssets"), to: "/governance/config-assets", icon: "N" },
      { label: t("templateAssets"), to: "/governance/template-assets", icon: "A" },
    ],
  },
  {
    label: t("enterpriseOps"),
    items: [
      { label: t("backupAndRestore"), to: "/ops/recovery", icon: "B" },
      { label: t("webhookSubscriptions"), to: "/ops/webhooks", icon: "W" },
      { label: t("alertRules"), to: "/ops/alerts", icon: "A" },
      { label: t("incidents"), to: "/ops/incidents", icon: "I" },
    ],
  },
  {
    label: t("compatibility"),
    items: [{ label: t("compatibility"), to: "/compatibility", icon: "C" }],
  },
  {
    label: t("platform"),
    items: [
      { label: t("semanticStoreProviders"), to: "/settings/semantic-store", icon: "E" },
      { label: t("observabilityExporters"), to: "/settings/observability-exporters", icon: "O" },
      { label: t("sandboxPolicies"), to: "/settings/sandbox-policies", icon: "X" },
      { label: t("containerPoolPolicies"), to: "/settings/container-pool-policies", icon: "C" },
      { label: t("settings"), to: "/settings", icon: "S" },
    ],
  },
]);

function toggleTheme() {
  preferences.setTheme(preferences.theme === "light" ? "dark" : "light");
}

function toggleLocale() {
  preferences.setLocale(preferences.locale === "zh-CN" ? "en-US" : "zh-CN");
}

async function logout() {
  await auth.logout();
  window.location.href = "/login";
}

function setTenant(event: Event) {
  scope.setTenant(Number((event.target as HTMLSelectElement).value));
  scopeVersion.value += 1;
}

function setProject(event: Event) {
  scope.setProject(Number((event.target as HTMLSelectElement).value));
  scopeVersion.value += 1;
}

function setEnvironment(event: Event) {
  scope.setEnvironment((event.target as HTMLSelectElement).value);
  scopeVersion.value += 1;
}

function scopeLabel(name: string | null | undefined, id: number) {
  return name || `#${id}`;
}

function animateContent() {
  if (!contentRef.value) return;
  ctx?.revert();
  ctx = gsap.context(() => {
    gsap.fromTo(
      ".page",
      { autoAlpha: 0, y: 10 },
      { autoAlpha: 1, y: 0, duration: 0.32, ease: "power1.out" },
    );
  }, contentRef.value);
}

onMounted(animateContent);
watch(() => route.fullPath, animateContent, { flush: "post" });
onUnmounted(() => ctx?.revert());
</script>

<style scoped>
.shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 284px minmax(0, 1fr);
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
  border-right: 1px solid var(--color-sidebar-border);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--color-sidebar-raised) 56%, transparent), transparent 28%),
    var(--color-sidebar);
  padding: 16px 12px;
  scrollbar-width: thin;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: var(--radius-md);
  color: var(--color-sidebar-text);
  padding: 8px;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-accent) 86%, var(--color-info));
  color: oklch(98% 0.006 255);
  font-weight: 800;
  box-shadow: 0 10px 24px color-mix(in srgb, var(--color-accent) 22%, transparent);
}

.brand strong,
.brand small {
  display: block;
}

.brand small {
  margin-top: 2px;
  color: var(--color-sidebar-muted);
  font-size: 11px;
}

.nav {
  display: grid;
  gap: 16px;
  margin-top: 24px;
}

.nav p {
  margin: 0 0 6px 9px;
  color: color-mix(in srgb, var(--color-sidebar-muted) 76%, transparent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 9px;
  border-radius: var(--radius-sm);
  color: var(--color-sidebar-muted);
  padding: 7px 8px;
  text-decoration: none;
}

.nav-glyph {
  display: grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--color-sidebar-border) 78%, transparent);
  border-radius: 5px;
  background: color-mix(in srgb, var(--color-sidebar-raised) 60%, transparent);
  font-size: 10px;
  font-weight: 800;
}

.nav-item:hover {
  background: color-mix(in srgb, var(--color-sidebar-raised) 74%, transparent);
  color: var(--color-sidebar-text);
}

.nav-item.router-link-active {
  border: 1px solid color-mix(in srgb, var(--color-accent) 44%, var(--color-sidebar-border));
  background: color-mix(in srgb, var(--color-accent) 18%, var(--color-sidebar-raised));
  color: var(--color-sidebar-text);
  font-weight: 700;
}

.nav-item.router-link-active .nav-glyph {
  border-color: color-mix(in srgb, var(--color-accent) 64%, var(--color-sidebar-border));
  background: color-mix(in srgb, var(--color-accent) 28%, transparent);
  color: oklch(91% 0.045 259);
}

.main {
  min-width: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-surface) 90%, transparent);
  padding: 11px 22px;
  backdrop-filter: blur(12px);
}

.context,
.actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.scope-selectors {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

label {
  display: grid;
  gap: 4px;
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.mode-pill {
  align-self: end;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-accent-quiet);
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
  padding: 7px 9px;
}

.mode-pill[data-mode="live"] {
  color: var(--color-success);
}

.mode-pill[data-mode="offline"] {
  color: var(--color-danger);
}

.operator-pill {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  color: var(--color-text);
  font-size: 12px;
  font-weight: 700;
  padding: 7px 9px;
}

.search {
  width: min(330px, 28vw);
}

.icon-button {
  min-width: 46px;
}

.content {
  padding: 22px 24px 30px;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: relative;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--color-sidebar-border);
  }

  .nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .context,
  .scope-selectors,
  .actions {
    flex-wrap: wrap;
  }

  .search {
    width: 100%;
  }
}

@media (max-width: 720px) {
  .nav {
    grid-template-columns: 1fr;
  }

  .content {
    padding: 18px 14px 24px;
  }
}
</style>
