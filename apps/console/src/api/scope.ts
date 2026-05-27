export type ConsoleScope = {
  tenant_id: string;
  project_id: string;
  environment: string;
};

export const SCOPE_KEY = "dimoorun.console.scope";

export function fallbackScope(): ConsoleScope {
  return {
    tenant_id: "tenant_1",
    project_id: "project_1",
    environment: "local",
  };
}

export function normalizeScopes(scopes: unknown): ConsoleScope[] {
  if (!Array.isArray(scopes)) return [fallbackScope()];
  const normalized = scopes
    .map((scope) => {
      if (!scope || typeof scope !== "object") return null;
      const record = scope as Record<string, unknown>;
      const tenantId = String(record.tenant_id || "");
      const projectId = String(record.project_id || "");
      const environment = String(record.environment || "");
      if (!tenantId || !projectId || !environment) return null;
      return { tenant_id: tenantId, project_id: projectId, environment };
    })
    .filter((scope): scope is ConsoleScope => Boolean(scope));
  return normalized.length > 0 ? normalized : [fallbackScope()];
}

export function scopeKey(scope: ConsoleScope): string {
  return `${scope.tenant_id}::${scope.project_id}::${scope.environment}`;
}

export function readCurrentScope(): ConsoleScope {
  const raw = localStorage.getItem(SCOPE_KEY);
  if (!raw) return fallbackScope();
  try {
    const [scope] = normalizeScopes([JSON.parse(raw)]);
    return scope;
  } catch {
    localStorage.removeItem(SCOPE_KEY);
    return fallbackScope();
  }
}

export function writeCurrentScope(scope: ConsoleScope): void {
  localStorage.setItem(SCOPE_KEY, JSON.stringify(scope));
}

export function clearCurrentScope(): void {
  localStorage.removeItem(SCOPE_KEY);
}
