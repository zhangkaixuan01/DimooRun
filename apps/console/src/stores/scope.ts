import { defineStore } from "pinia";

import {
  clearCurrentScope,
  fallbackScope,
  normalizeScopes,
  readCurrentScope,
  scopeKey,
  writeCurrentScope,
  type ConsoleScope,
} from "../api/scope";

export const useScopeStore = defineStore("scope", {
  state: () => ({
    allowedScopes: normalizeScopes([]),
    currentScope: readCurrentScope(),
  }),
  getters: {
    tenantOptions: (state) => uniqueBy(state.allowedScopes, (scope) => scope.tenant_id),
    projectOptions: (state) =>
      uniqueBy(
        state.allowedScopes.filter((scope) => scope.tenant_id === state.currentScope.tenant_id),
        (scope) => scope.project_id,
      ),
    environmentOptions: (state) =>
      uniqueBy(
        state.allowedScopes.filter(
          (scope) =>
            scope.tenant_id === state.currentScope.tenant_id &&
            scope.project_id === state.currentScope.project_id,
        ),
        (scope) => scope.environment,
      ),
  },
  actions: {
    initialize(scopes: unknown) {
      this.allowedScopes = normalizeScopes(scopes);
      const stored = readCurrentScope();
      const storedAllowedScope = this.allowedScopes.find((scope) => scopeKey(scope) === scopeKey(stored));
      this.currentScope = storedAllowedScope || this.allowedScopes[0] || fallbackScope();
      writeCurrentScope(this.currentScope);
    },
    setTenant(tenantId: number) {
      const next =
        this.allowedScopes.find((scope) => scope.tenant_id === tenantId) || this.allowedScopes[0];
      if (next) this.setScope(next);
    },
    setProject(projectId: number) {
      const next =
        this.allowedScopes.find(
          (scope) => scope.tenant_id === this.currentScope.tenant_id && scope.project_id === projectId,
        ) || this.currentScope;
      this.setScope(next);
    },
    setEnvironment(environment: string) {
      const next =
        this.allowedScopes.find(
          (scope) =>
            scope.tenant_id === this.currentScope.tenant_id &&
            scope.project_id === this.currentScope.project_id &&
            scope.environment === environment,
        ) || this.currentScope;
      this.setScope(next);
    },
    setScope(scope: ConsoleScope) {
      this.currentScope = scope;
      writeCurrentScope(scope);
      window.dispatchEvent(new CustomEvent("dimoorun:scope-changed", { detail: scope }));
    },
    clear() {
      this.allowedScopes = normalizeScopes([]);
      this.currentScope = fallbackScope();
      clearCurrentScope();
    },
  },
});

function uniqueBy(scopes: ConsoleScope[], keyOf: (scope: ConsoleScope) => unknown): ConsoleScope[] {
  const seen = new Set<string>();
  return scopes.filter((scope) => {
    const key = String(keyOf(scope));
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
