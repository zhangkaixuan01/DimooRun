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
            <span>{{ item.icon }}</span>
            {{ item.label }}
          </RouterLink>
        </section>
      </nav>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="context">
          <label>
            {{ t("tenant") }}
            <select class="select">
              <option>default</option>
            </select>
          </label>
          <label>
            {{ t("project") }}
            <select class="select">
              <option>customer-support</option>
            </select>
          </label>
          <label>
            {{ t("environment") }}
            <select class="select">
              <option>prod</option>
              <option>staging</option>
              <option>dev</option>
            </select>
          </label>
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
        </div>
      </header>

      <main ref="contentRef" class="content">
        <RouterView />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { gsap } from "gsap";
import { useRoute } from "vue-router";

import { useI18n } from "../i18n/useI18n";
import { usePreferencesStore } from "../stores/preferences";

const preferences = usePreferencesStore();
const { t } = useI18n();
const route = useRoute();
const contentRef = ref<HTMLElement | null>(null);
let ctx: gsap.Context | undefined;

preferences.hydrateDocument();

const navGroups = computed(() => [
  {
    label: t("overview"),
    items: [{ label: t("dashboard"), to: "/dashboard", icon: "O" }],
  },
  {
    label: t("runtime"),
    items: [
      { label: t("agents"), to: "/agents", icon: "A" },
      { label: t("deployments"), to: "/deployments", icon: "D" },
      { label: t("compatibility"), to: "/compatibility", icon: "C" },
      { label: t("publishedSurfaces"), to: "/published-surfaces", icon: "P" },
      { label: t("runs"), to: "/runs", icon: "R" },
      { label: t("tasks"), to: "/tasks", icon: "T" },
    ],
  },
  {
    label: t("observability"),
    items: [
      { label: t("events"), to: "/events", icon: "E" },
      { label: t("replay"), to: "/replay", icon: "B" },
    ],
  },
  {
    label: t("governance"),
    items: [
      { label: t("humanTasks"), to: "/governance/human-tasks", icon: "H" },
      { label: t("policies"), to: "/governance/policies", icon: "G" },
      { label: t("apiKeys"), to: "/governance/api-keys", icon: "K" },
    ],
  },
  {
    label: t("platform"),
    items: [{ label: t("settings"), to: "/settings", icon: "S" }],
  },
]);

function toggleTheme() {
  preferences.setTheme(preferences.theme === "light" ? "dark" : "light");
}

function toggleLocale() {
  preferences.setLocale(preferences.locale === "zh-CN" ? "en-US" : "zh-CN");
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
  grid-template-columns: 260px minmax(0, 1fr);
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
  border-right: 1px solid var(--color-border);
  background: var(--color-surface);
  padding: 18px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: #ffffff;
  font-weight: 800;
}

.brand strong,
.brand small {
  display: block;
}

.brand small {
  margin-top: 2px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.nav {
  display: grid;
  gap: 18px;
  margin-top: 24px;
}

.nav p {
  margin: 0 0 7px 8px;
  color: var(--color-text-soft);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 9px;
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  padding: 7px 9px;
  text-decoration: none;
}

.nav-item span {
  display: grid;
  width: 20px;
  height: 20px;
  place-items: center;
  border: 1px solid var(--color-border);
  border-radius: 5px;
  font-size: 10px;
  font-weight: 800;
}

.nav-item.router-link-active {
  background: var(--color-accent-soft);
  color: var(--color-text);
  font-weight: 700;
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
  background: color-mix(in srgb, var(--color-page) 88%, transparent);
  padding: 12px 20px;
  backdrop-filter: blur(14px);
}

.context,
.actions {
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

.search {
  width: min(330px, 28vw);
}

.icon-button {
  min-width: 46px;
}

.content {
  padding: 22px;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: relative;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  .nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .context,
  .actions {
    flex-wrap: wrap;
  }

  .search {
    width: 100%;
  }
}
</style>
