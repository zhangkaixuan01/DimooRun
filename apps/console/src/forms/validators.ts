export type ValidationError = {
  field: string;
  message: string;
};

type FormRecord = Record<string, unknown>;

export function validateAgentVersionForm(form: FormRecord): ValidationError[] {
  return [
    required(form, "version", "Version is required."),
    required(form, "package_uri", "Package URI is required."),
    required(form, "framework", "Framework is required."),
    required(form, "adapter", "Adapter is required."),
    required(form, "entrypoint", "Entrypoint is required."),
  ].filter(Boolean) as ValidationError[];
}

export function validateDeploymentConfig(form: FormRecord): ValidationError[] {
  const errors = [
    required(form, "environment", "Environment is required."),
  ].filter(Boolean) as ValidationError[];
  if (Number(form.replicas || 0) < 1) {
    errors.push({ field: "replicas", message: "Replicas must be at least 1." });
  }
  if (!isObject(form.config)) {
    errors.push({ field: "config", message: "Config must be a JSON object." });
  }
  return errors;
}

export function validatePolicyCondition(form: FormRecord): ValidationError[] {
  return [
    required(form, "resource_type", "Resource type is required."),
    required(form, "action", "Action is required."),
    required(form, "decision", "Decision is required."),
    objectField(form, "condition", "Condition must be a JSON object."),
  ].filter(Boolean) as ValidationError[];
}

export function validateModelGatewayForm(form: FormRecord): ValidationError[] {
  return [
    required(form, "name", "Name is required."),
    required(form, "provider_type", "Provider type is required."),
    required(form, "credential_ref", "Credential reference is required."),
  ].filter(Boolean) as ValidationError[];
}

export function validateToolSchema(form: FormRecord): ValidationError[] {
  return [
    required(form, "name", "Name is required."),
    objectField(form, "schema", "Schema must be a JSON object."),
    required(form, "risk_level", "Risk level is required."),
  ].filter(Boolean) as ValidationError[];
}

export function validateSecretRef(form: FormRecord): ValidationError[] {
  const errors = [
    required(form, "name", "Name is required."),
    required(form, "provider", "Provider is required."),
    required(form, "ref", "Secret reference is required."),
  ].filter(Boolean) as ValidationError[];
  if (typeof form.ref === "string" && !form.ref.includes("://")) {
    errors.push({ field: "ref", message: "Secret reference must use an external provider URI." });
  }
  return errors;
}

export function validateReplayRequest(form: FormRecord): ValidationError[] {
  return [
    positiveNumber(form, "source_run_id", "Source run is required."),
    positiveNumber(form, "candidate_agent_version_id", "Candidate agent version is required."),
  ].filter(Boolean) as ValidationError[];
}

export function validateExperimentForm(form: FormRecord): ValidationError[] {
  return [
    required(form, "name", "Name is required."),
    positiveNumber(form, "dataset_id", "Dataset is required."),
    positiveNumber(form, "candidate_agent_version_id", "Candidate agent version is required."),
    objectField(form, "evaluator_config", "Evaluator config must be a JSON object."),
  ].filter(Boolean) as ValidationError[];
}

export function validateBackupPlanForm(form: FormRecord): ValidationError[] {
  const errors = [
    required(form, "name", "Name is required."),
    required(form, "schedule", "Schedule is required."),
  ].filter(Boolean) as ValidationError[];
  if (Number(form.retention_days || 0) < 1) {
    errors.push({ field: "retention_days", message: "Retention days must be at least 1." });
  }
  if (!Array.isArray(form.targets) || form.targets.length === 0) {
    errors.push({ field: "targets", message: "At least one backup target is required." });
  }
  return errors;
}

export function validateRestoreJobForm(form: FormRecord): ValidationError[] {
  return [
    required(form, "backup_ref", "Backup reference is required."),
    required(form, "restore_scope", "Restore scope is required."),
    form.dry_run === true ? null : { field: "dry_run", message: "Restore must start as a dry run." },
  ].filter(Boolean) as ValidationError[];
}

function required(form: FormRecord, field: string, message: string): ValidationError | null {
  return typeof form[field] === "string" ? (String(form[field]).trim() ? null : { field, message }) : form[field] ? null : { field, message };
}

function positiveNumber(form: FormRecord, field: string, message: string): ValidationError | null {
  return Number(form[field] || 0) > 0 ? null : { field, message };
}

function objectField(form: FormRecord, field: string, message: string): ValidationError | null {
  return isObject(form[field]) ? null : { field, message };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}
