export type ConsoleScope = {
  tenant_id: number;
  tenant_name?: string | null;
  project_id: number;
  project_name?: string | null;
  environment: string;
  environment_name?: string | null;
};

export const SCOPE_KEY = "dimoorun.console.scope";

export function fallbackScope(): ConsoleScope {
  return {
    tenant_id: 1,
    project_id: 1,
    environment: "local",
  };
}

export function normalizeScopes(scopes: unknown): ConsoleScope[] {
  if (!Array.isArray(scopes)) return [fallbackScope()];
  const normalized = scopes
    .map((scope): ConsoleScope | null => {
      if (!scope || typeof scope !== "object") return null;
      const record = scope as Record<string, unknown>;
      const tenantId = Number(record.tenant_id || 0);
      const projectId = Number(record.project_id || 0);
      const environment = String(record.environment || "");
      if (!tenantId || !projectId || !environment) return null;
      return {
        tenant_id: tenantId,
        tenant_name: optionalText(record.tenant_name),
        project_id: projectId,
        project_name: optionalText(record.project_name),
        environment,
        environment_name: optionalText(record.environment_name),
      };
    })
    .filter((scope): scope is ConsoleScope => Boolean(scope));
  return normalized.length > 0 ? normalized : [fallbackScope()];
}

function optionalText(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  return text.length > 0 ? text : null;
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
