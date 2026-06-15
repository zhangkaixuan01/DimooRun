<template>
  <div class="shell">
    <aside class="sidebar" :aria-label="t('primaryNav')">
      <div class="sidebar-head">
        <RouterLink class="brand" to="/dashboard">
          <span class="brand-mark">D</span>
          <span>
            <strong>DimooRun</strong>
            <small>{{ t("runtimeControlPlane") }}</small>
          </span>
        </RouterLink>
        <button
          class="button mobile-nav-toggle"
          type="button"
          :aria-expanded="mobileNavOpen"
          :aria-label="t('primaryNav')"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          {{ mobileNavOpen ? t("close") : t("menu") }}
        </button>
      </div>

      <nav class="nav" :class="{ open: mobileNavOpen }">
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
          <form class="search-form" role="search" @submit.prevent="submitGlobalSearch">
            <input
              v-model="searchQuery"
              class="input search"
              list="global-search-routes"
              :aria-label="t('globalSearchLabel')"
              :placeholder="t('globalSearch')"
            />
            <datalist id="global-search-routes">
              <option v-for="item in searchableRoutes" :key="item.to" :value="item.label" />
            </datalist>
            <span v-if="searchError" class="search-error" role="status">{{ searchError }}</span>
          </form>
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
import { useRoute, useRouter } from "vue-router";

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
const router = useRouter();
const contentRef = ref<HTMLElement | null>(null);
const scopeVersion = ref(0);
const mobileNavOpen = ref(false);
const searchQuery = ref("");
const searchError = ref("");
const mode = apiMode();
const modeLabel = computed(() => (mode === "live" ? t("live") : t("offline")));
const showScopeSelector = computed(() => {
  const path = route.path;
  if (path.startsWith("/identity")) return false;
  if (path === "/settings") return false;
  return true;
});
let ctx: gsap.Context | undefined;
let refreshTimer: number | undefined;

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
      { label: t("packages"), to: "/packages/register", icon: "K" },
      { label: t("deployments"), to: "/deployments", icon: "D" },
      { label: t("publishedSurfaces"), to: "/published-surfaces", icon: "P" },
      { label: t("workers"), to: "/runtime/workers", icon: "W" },
      { label: t("agentInstances"), to: "/runtime/agent-instances", icon: "I" },
      { label: t("capacity"), to: "/runtime/capacity", icon: "C" },
      { label: t("scheduledRuns"), to: "/runtime/schedules", icon: "S" },
      { label: t("batchRuns"), to: "/runtime/batches", icon: "U" },
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
      { label: t("cost"), to: "/observability/costs", icon: "$" },
      { label: t("budget"), to: "/observability/budgets", icon: "B" },
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
      { label: t("platformSettings"), to: "/settings/platform", icon: "P" },
      { label: t("providerStatus"), to: "/settings/providers", icon: "V" },
      { label: t("dangerZone"), to: "/settings/danger-zone", icon: "!" },
      { label: t("semanticStoreProviders"), to: "/settings/semantic-store", icon: "E" },
      { label: t("observabilityExporters"), to: "/settings/observability-exporters", icon: "O" },
      { label: t("sandboxPolicies"), to: "/settings/sandbox-policies", icon: "X" },
      { label: t("containerPoolPolicies"), to: "/settings/container-pool-policies", icon: "C" },
      { label: t("settings"), to: "/settings", icon: "S" },
    ],
  },
]);

const searchableRoutes = computed(() => navGroups.value.flatMap((group) => group.items));

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

function submitGlobalSearch() {
  const query = searchQuery.value.trim().toLowerCase();
  searchError.value = "";
  if (!query) return;

  const match = searchableRoutes.value.find((item) => {
    const label = item.label.toLowerCase();
    const path = item.to.toLowerCase();
    return label === query || path === query || label.includes(query) || path.includes(query);
  });

  if (!match) {
    searchError.value = t("searchNoMatch");
    return;
  }

  searchQuery.value = "";
  router.push(match.to);
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

function refreshCurrentView() {
  if (route.meta.public) return;
  scopeVersion.value += 1;
}

function startLiveRefresh() {
  stopLiveRefresh();
  if (!preferences.liveRefresh) return;
  refreshTimer = window.setInterval(refreshCurrentView, 30000);
}

function stopLiveRefresh() {
  if (refreshTimer === undefined) return;
  window.clearInterval(refreshTimer);
  refreshTimer = undefined;
}

onMounted(() => {
  animateContent();
  startLiveRefresh();
});
watch(() => route.fullPath, animateContent, { flush: "post" });
watch(() => route.fullPath, () => {
  mobileNavOpen.value = false;
});
watch(() => preferences.liveRefresh, startLiveRefresh);
onUnmounted(() => {
  stopLiveRefresh();
  ctx?.revert();
});
</script>

<style scoped>
.shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 260px minmax(0, 1fr);
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
  border-right: 1px solid var(--color-sidebar-border);
  background: var(--color-sidebar);
  padding: 14px 10px;
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

.sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-nav-toggle {
  display: none;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: oklch(98% 0.006 255);
  font-weight: 800;
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
  padding: 10px 18px;
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

.search-form {
  position: relative;
  min-width: min(300px, 24vw);
}

.search {
  width: min(300px, 24vw);
}

.search-error {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 30;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  color: var(--color-danger);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 8px;
  white-space: nowrap;
}

.icon-button {
  min-width: 46px;
}

.content {
  padding: 18px 20px 28px;
}

@media (max-width: 1080px) {
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

  .search-form,
  .search {
    width: 100%;
  }
}

@media (max-width: 720px) {
  .sidebar {
    padding: 10px;
  }

  .mobile-nav-toggle {
    display: inline-flex;
    min-width: 74px;
  }

  .nav {
    display: none;
    grid-template-columns: 1fr;
    margin-top: 12px;
  }

  .nav.open {
    display: grid;
    max-height: min(68vh, 620px);
    overflow: auto;
    padding-right: 2px;
  }

  .content {
    padding: 18px 14px 24px;
  }
}
</style>
