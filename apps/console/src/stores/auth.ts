import { defineStore } from "pinia";

import { consoleClient, toConsoleApiError, type ConsoleApiError, type ConsoleOperator } from "../api/client";
import { useScopeStore } from "./scope";

const TOKEN_KEY = "dimoorun.console.token";
const OPERATOR_KEY = "dimoorun.console.operator";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY),
    operator: readOperator(),
    loading: false,
    error: null as ConsoleApiError | null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.operator),
    can: (state) => (permission: string) =>
      Boolean(
        state.operator?.permissions.includes("*") ||
          state.operator?.permissions.includes(permission),
      ),
  },
  actions: {
    async login(email: string, password: string) {
      this.loading = true;
      this.error = null;
      try {
        const payload = await consoleClient.login(email, password);
        this.token = payload.access_token;
        this.operator = payload.operator;
        localStorage.setItem(TOKEN_KEY, payload.access_token);
        localStorage.setItem(OPERATOR_KEY, JSON.stringify(payload.operator));
        useScopeStore().initialize(payload.operator.allowed_scopes);
      } catch (caught) {
        this.error = toConsoleApiError(caught);
        throw caught;
      } finally {
        this.loading = false;
      }
    },
    async hydrateSession() {
      if (!this.token) return;
      this.loading = true;
      this.error = null;
      try {
        const operator = await consoleClient.me();
        this.operator = operator;
        localStorage.setItem(OPERATOR_KEY, JSON.stringify(operator));
        useScopeStore().initialize(operator.allowed_scopes);
      } catch (caught) {
        this.clearSession();
      } finally {
        this.loading = false;
      }
    },
    async logout() {
      try {
        await consoleClient.logout();
      } finally {
        this.clearSession();
      }
    },
    async changePassword(currentPassword: string, newPassword: string) {
      this.loading = true;
      this.error = null;
      try {
        await consoleClient.changePassword(currentPassword, newPassword);
        this.clearSession();
      } catch (caught) {
        this.error = toConsoleApiError(caught);
        throw caught;
      } finally {
        this.loading = false;
      }
    },
    clearSession() {
      this.token = null;
      this.operator = null;
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(OPERATOR_KEY);
      useScopeStore().clear();
    },
  },
});

function readOperator(): ConsoleOperator | null {
  const raw = localStorage.getItem(OPERATOR_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ConsoleOperator;
  } catch {
    localStorage.removeItem(OPERATOR_KEY);
    return null;
  }
}
