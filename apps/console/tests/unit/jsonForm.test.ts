import { describe, expect, it } from "vitest";

import { parseJsonObject, updateJsonText } from "../../src/forms/jsonForm";
import {
  validateAgentVersionForm,
  validateBackupPlanForm,
  validateDeploymentConfig,
  validateExperimentForm,
  validateModelGatewayForm,
  validatePolicyCondition,
  validateReplayRequest,
  validateRestoreJobForm,
  validateSecretRef,
  validateToolSchema,
} from "../../src/forms/validators";

describe("jsonForm", () => {
  it("parses JSON objects and reports exact syntax position", () => {
    expect(parseJsonObject('{"ok": true}')).toEqual({ ok: true });
    const result = parseJsonObject('{"ok": ');

    expect(result).toMatchObject({
      ok: false,
      line: 1,
      column: 8,
    });
    expect(result.message).toContain("Invalid JSON");
  });

  it("updates JSON text without losing the previous valid value", () => {
    const state = updateJsonText({ lastValidValue: { retries: 1 } }, '{"retries": 2}');
    expect(state.lastValidValue).toEqual({ retries: 2 });
    expect(state.error).toBeNull();

    const invalid = updateJsonText(state, '{"retries": ');
    expect(invalid.lastValidValue).toEqual({ retries: 2 });
    expect(invalid.error?.column).toBe(13);
  });
});

describe("high-risk form validators", () => {
  it("validates required production workflow forms", () => {
    expect(validateAgentVersionForm({ version: "1.0.0", package_uri: "oci://agent", framework: "langgraph", adapter: "langgraph", entrypoint: "agent:create_agent" })).toEqual([]);
    expect(validateDeploymentConfig({ environment: "prod", replicas: 2, config: {} })).toEqual([]);
    expect(validatePolicyCondition({ resource_type: "deployment", action: "promote", decision: "allow", condition: {} })).toEqual([]);
    expect(validateModelGatewayForm({ name: "openai", provider_type: "openai", credential_ref: "secret:model" })).toEqual([]);
    expect(validateToolSchema({ name: "search", schema: { type: "object" }, risk_level: "read" })).toEqual([]);
    expect(validateSecretRef({ name: "model", provider: "external", ref: "vault://model" })).toEqual([]);
    expect(validateReplayRequest({ source_run_id: 1, candidate_agent_version_id: 2 })).toEqual([]);
    expect(validateExperimentForm({ name: "quality", dataset_id: 1, candidate_agent_version_id: 2, evaluator_config: {} })).toEqual([]);
    expect(validateBackupPlanForm({ name: "daily", schedule: "0 0 * * *", retention_days: 7, targets: ["postgres"] })).toEqual([]);
    expect(validateRestoreJobForm({ backup_ref: "backup://daily/1", restore_scope: "project", dry_run: true })).toEqual([]);
  });

  it("returns field-specific errors for invalid forms", () => {
    expect(validateDeploymentConfig({ environment: "", replicas: 0, config: [] })).toEqual([
      { field: "environment", message: "Environment is required." },
      { field: "replicas", message: "Replicas must be at least 1." },
      { field: "config", message: "Config must be a JSON object." },
    ]);
    expect(validateSecretRef({ name: "", provider: "external", ref: "plaintext-secret" })).toContainEqual({
      field: "ref",
      message: "Secret reference must use an external provider URI.",
    });
  });
});
