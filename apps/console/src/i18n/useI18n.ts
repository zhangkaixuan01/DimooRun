import { computed } from "vue";

import { messages, type MessageKey } from "./messages";
import { usePreferencesStore } from "../stores/preferences";

export function useI18n() {
  const preferences = usePreferencesStore();
  const currentMessages = computed(() => messages[preferences.locale]);

  function t(key: MessageKey): string {
    return currentMessages.value[key] ?? key;
  }

  return { t, locale: computed(() => preferences.locale) };
}
