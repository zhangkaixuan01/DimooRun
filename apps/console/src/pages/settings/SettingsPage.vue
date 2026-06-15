<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("platformArea") }}</p>
        <h1 class="page-title">{{ t("settings") }}</h1>
      </div>
    </header>
    <div class="overview-grid">
      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("consolePreferences") }}</p>
            <h2>{{ t("preferences") }}</h2>
          </div>
        </header>
        <div class="panel-body settings">
          <label>{{ t("themePreference") }}<select v-model="preferences.theme" class="select" @change="preferences.setTheme(preferences.theme)"><option value="light">{{ t("light") }}</option><option value="dark">{{ t("dark") }}</option></select></label>
          <label>{{ t("languagePreference") }}<select v-model="preferences.locale" class="select" @change="preferences.setLocale(preferences.locale)"><option value="zh-CN">{{ t("chinese") }}</option><option value="en-US">{{ t("english") }}</option></select></label>
        </div>
      </section>
      <section class="panel">
        <header class="panel-header">
          <div>
            <p class="page-kicker">{{ t("platformWorkflows") }}</p>
            <h2>{{ t("controlSurfaces") }}</h2>
          </div>
        </header>
        <div class="panel-body link-list">
          <RouterLink class="setting-link" to="/settings/platform">{{ t("platformSettings") }}</RouterLink>
          <RouterLink class="setting-link" to="/settings/providers">{{ t("providerStatus") }}</RouterLink>
          <RouterLink class="setting-link" to="/settings/danger-zone">{{ t("dangerZone") }}</RouterLink>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";

import { useI18n } from "../../i18n/useI18n";
import { usePreferencesStore } from "../../stores/preferences";

const preferences = usePreferencesStore();
const { t } = useI18n();
</script>

<style scoped>
.settings {
  display: grid;
  gap: 14px;
}

.overview-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

label {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-weight: 600;
}

.link-list {
  display: grid;
  gap: 10px;
}

.setting-link {
  display: flex;
  min-height: 42px;
  align-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  color: var(--color-text);
  font-weight: 700;
  padding: 0 12px;
  text-decoration: none;
}

.setting-link:hover {
  border-color: color-mix(in srgb, var(--color-accent) 44%, var(--color-border));
  background: var(--color-accent-quiet);
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
