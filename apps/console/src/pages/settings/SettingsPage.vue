<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="page-kicker">{{ t("consolePreferences") }}</p>
        <h1 class="page-title">{{ t("settings") }}</h1>
      </div>
    </header>
    <section class="panel">
      <div class="panel-body settings">
        <label>{{ t("themePreference") }}<select v-model="preferences.theme" class="select" @change="preferences.setTheme(preferences.theme)"><option value="light">{{ t("light") }}</option><option value="dark">{{ t("dark") }}</option></select></label>
        <label>{{ t("languagePreference") }}<select v-model="preferences.locale" class="select" @change="preferences.setLocale(preferences.locale)"><option value="zh-CN">{{ t("chinese") }}</option><option value="en-US">{{ t("english") }}</option></select></label>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from "../../i18n/useI18n";
import { usePreferencesStore } from "../../stores/preferences";

const preferences = usePreferencesStore();
const { t } = useI18n();
</script>

<style scoped>
.settings {
  display: grid;
  max-width: 420px;
  gap: 14px;
}

label {
  display: grid;
  gap: 6px;
  color: var(--color-text-muted);
  font-weight: 700;
}
</style>
