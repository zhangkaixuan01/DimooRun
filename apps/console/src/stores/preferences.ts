import { defineStore } from "pinia";

import type { Locale } from "../i18n/messages";

export type ThemeMode = "light" | "dark";

const localeKey = "dimoorun.console.locale";
const themeKey = "dimoorun.console.theme";

function readLocale(): Locale {
  const stored = localStorage.getItem(localeKey);
  return stored === "en-US" || stored === "zh-CN" ? stored : "zh-CN";
}

function readTheme(): ThemeMode {
  const stored = localStorage.getItem(themeKey);
  return stored === "dark" || stored === "light" ? stored : "light";
}

export const usePreferencesStore = defineStore("preferences", {
  state: () => ({
    locale: readLocale() as Locale,
    theme: readTheme() as ThemeMode,
    liveRefresh: true,
  }),
  actions: {
    setLocale(locale: Locale) {
      this.locale = locale;
      localStorage.setItem(localeKey, locale);
      document.documentElement.lang = locale === "zh-CN" ? "zh-CN" : "en";
    },
    setTheme(theme: ThemeMode) {
      this.theme = theme;
      localStorage.setItem(themeKey, theme);
      document.documentElement.dataset.theme = theme;
    },
    toggleLiveRefresh() {
      this.liveRefresh = !this.liveRefresh;
    },
    hydrateDocument() {
      document.documentElement.lang = this.locale === "zh-CN" ? "zh-CN" : "en";
      document.documentElement.dataset.theme = this.theme;
    },
  },
});
