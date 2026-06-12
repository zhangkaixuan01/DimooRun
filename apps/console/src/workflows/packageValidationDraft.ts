const STORAGE_KEY = "dimoorun.console.packageValidationDraft";

export type ReadyVersionDraft = {
  packageUri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  manifest: Record<string, unknown>;
  capabilities: Record<string, unknown>;
  validationToken: string;
  nextAction: string;
  warnings: string[];
};

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

export function readReadyVersionDraft(): ReadyVersionDraft | null {
  if (!canUseStorage()) return null;
  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ReadyVersionDraft;
    if (
      typeof parsed.packageUri !== "string"
      || typeof parsed.framework !== "string"
      || typeof parsed.adapter !== "string"
      || typeof parsed.entrypoint !== "string"
      || typeof parsed.validationToken !== "string"
      || !parsed.manifest
      || typeof parsed.manifest !== "object"
      || Array.isArray(parsed.manifest)
      || !parsed.capabilities
      || typeof parsed.capabilities !== "object"
      || Array.isArray(parsed.capabilities)
      || !Array.isArray(parsed.warnings)
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function writeReadyVersionDraft(value: ReadyVersionDraft): void {
  if (!canUseStorage()) return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

export function clearReadyVersionDraft(): void {
  if (!canUseStorage()) return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}
