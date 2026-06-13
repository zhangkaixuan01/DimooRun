import type {
  Agent,
  AgentVersion,
  BackupDryRunResult,
  CompatibilityExplorerResult,
  CompatibilityMigrationResponse,
  ConsoleRuntimeOverview,
  ConsoleWriteOptions,
  DatasetCapture,
  DashboardSummary,
  Deployment,
  DeploymentPromotionPreview,
  ExperimentRunResult,
  HumanTask,
  IncidentWorkflowResult,
  IngressRouteTestResult,
  ModelGatewayTestResult,
  NotificationTestResult,
  PackageValidationResult,
  PolicyActivation,
  PolicyDraft,
  PolicySimulation,
  PublishedSurfaceDetail,
  PublishedSurfacePublishResult,
  PublishedSurfaceRolloutResult,
  PublishValidationResult,
  QualityGatePreview,
  ReplayComparison,
  ResourceId,
  RestoreDryRunResult,
  Run,
  RunAttempt,
  RunDatasetCapture,
  RuntimeAgentInstance,
  RuntimeAgentInstanceDetail,
  RuntimeCapacitySummary,
  RuntimeControlAction,
  RuntimeEvent,
  RuntimeQueuePressure,
  RuntimeWorker,
  RuntimeWorkerDetail,
  RuntimeMetricsSnapshot,
  SecretRotationResult,
  SecretValidationResult,
  Task,
  TaskCreateResult,
  ToolDryRunResult,
} from "./types";
import {
  type ConsoleDashboardSummaryRead,
  createDimooRunClient,
  DimooRunApiError,
  type ConsoleLoginResponse,
  type ConsoleOperatorRead,
  type NativeAgentRead,
  type NativeAgentVersionRead,
  type DeploymentPromotePayload,
  type DeploymentPromotionPreviewRead,
  type DeploymentRollbackPayload,
  type DatasetCapturePayload,
  type NativeDeploymentCreatePayload,
  type NativeDeploymentRead,
  type NativeDeploymentTaskCreatePayload,
  type NativeDeploymentUpdatePayload,
  type NativeEventRead,
  type PackageValidationPayload,
  type NativeRunRead,
  type NativeTaskCreatePayload,
  type NativeTaskRead,
  type ReplayComparisonRead,
  type ReplayComparisonRequest,
} from "./generated/dimoorun";
import { readCurrentScope, SCOPE_KEY, type ConsoleScope } from "./scope";

export type CursorPage<T> = {
  items: T[];
  nextCursor: string | null;
};

export type ApiMode = "live" | "offline";

export type ConsoleApiError = {
  errorCode: string;
  message: string;
  requestId: string | null;
  details: Record<string, unknown> | null;
};

type ConsoleRuntimeOverviewResponse = {
  summary: ConsoleDashboardSummaryRead;
  recent_failures: Array<{
    run_id: ResourceId;
    deployment_id: ResourceId | null;
    agent_id: ResourceId;
    agent_version_id: ResourceId;
    status: string;
    error_summary: string;
    created_at: string;
  }>;
  pending_actions: Array<{
    resource_type: string;
    resource_id: ResourceId;
    action: string;
    label: string;
    disabled_reason: string | null;
    required_permissions: string[];
    audit_required: boolean;
  }>;
  trend_points: Array<{
    label: string;
    runs: number;
    success_rate: number;
  }>;
};

export type AdminResource = Record<string, unknown> & {
  id: ResourceId;
  status?: string;
  name?: string;
  created_at?: string;
  updated_at?: string;
};

export type ConsoleOperator = ConsoleOperatorRead;
export type ConsoleLogin = ConsoleLoginResponse;
export type ConsoleOperatorSession = AdminResource & {
  operator_id: ResourceId;
  status: string;
  last_used_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoke_reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
};
export type RolePermissionMatrix = {
  items: AdminResource[];
  permissions: AdminResource[];
  request_id: string | null;
};
export type RolePermissionPreview = {
  role_id: ResourceId;
  role_name: string;
  current_permissions: string[];
  preview_permissions: string[];
  change: {
    added: string[];
    removed: string[];
    unchanged: string[];
  };
  affected_operators: Array<{
    operator_id: ResourceId;
    email: string;
    name: string;
    current_permissions?: string[];
    preview_permissions?: string[];
  }>;
  affected_service_accounts: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  policy_conflicts: Array<Record<string, unknown>>;
};
export type OperatorAccessDetail = {
  item: ConsoleOperator & {
    active_sessions: ConsoleOperatorSession[];
    api_keys_created: AdminResource[];
    recent_audit_actions: AdminResource[];
    disable_impact: {
      active_session_count: number;
      api_keys_created_count: number;
    };
  };
  request_id: string | null;
};
export type ServiceAccountDetail = {
  item: AdminResource & {
    tenant_id: number;
    project_id: number | null;
    permissions: string[];
    last_used_at: string | null;
    api_keys: Array<AdminResource & { scope_diff?: Record<string, unknown> }>;
    dependent_deployments: Array<Record<string, unknown>>;
  };
  request_id: string | null;
};
export type MachineApiKeyCreate = {
  item: AdminResource;
  plain_key: string;
  request_id: string | null;
};
export type PlatformScopedSetting = {
  id: ResourceId;
  tenant_id: number;
  project_id: number | null;
  environment: string | null;
  scope_kind: "organization" | "project" | "environment";
  setting_key: string;
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  updated_at: string | null;
};
export type PlatformSettingsSnapshot = {
  runtime_mode: string;
  runtime_environment: string;
  database_mode: string;
  queue_backend: string;
  object_store: Record<string, unknown>;
  secret_provider: Record<string, unknown>;
  model_gateway_provider: Record<string, unknown>;
  artifact_retention: Record<string, unknown>;
  trace_retention: Record<string, unknown>;
  cors: Record<string, unknown>;
  runtime_write_protected: boolean;
  production_safety: { status: string; warnings: string[] };
  scope_defaults: PlatformScopedSetting[];
  danger_state: Record<string, unknown>;
};
export type ProviderStatus = {
  provider: string;
  status: string;
  summary: string;
  reason: string;
};
export type DangerousActionPreview = {
  action: string;
  scope_kind: string;
  risk_level: string;
  available: boolean;
  blocked_reasons: string[];
  confirmation_phrase: string;
  affected_resources: Array<{ label: string; count: number }>;
  rollback_notes: string;
  audit_required: boolean;
};
export type DangerousActionResult = {
  action: string;
  status: string;
  scope_setting?: PlatformScopedSetting;
  rollback_notes: string;
  request_id: string | null;
};

const TOKEN_KEY = "dimoorun.console.token";
const OPERATOR_KEY = "dimoorun.console.operator";
const API_BASE_OVERRIDE_KEY = "dimoorun.console.apiBaseUrlOverride";

function page<T>(items: T[]): CursorPage<T> {
  return { items, nextCursor: null };
}

export function apiBaseUrl(): string | null {
  if (typeof window !== "undefined") {
    const override = window.sessionStorage.getItem(API_BASE_OVERRIDE_KEY);
    if (override !== null) {
      return override.trim() || null;
    }
  }
  return import.meta.env.VITE_DIMOORUN_API_BASE_URL || null;
}

export function apiMode(): ApiMode {
  return apiBaseUrl() ? "live" : "offline";
}

export function isApiConfigured(): boolean {
  return apiMode() === "live";
}

export function toConsoleApiError(error: unknown): ConsoleApiError {
  if (error instanceof DimooRunApiError) {
    return {
      errorCode: error.errorCode || `http_${error.status}`,
      message: error.message,
      requestId: error.requestId,
      details: error.details,
    };
  }
  if (isRecord(error) && typeof error.errorCode === "string" && typeof error.message === "string") {
    return {
      errorCode: error.errorCode,
      message: error.message,
      requestId: typeof error.requestId === "string" ? error.requestId : null,
      details: isRecord(error.details) ? error.details : null,
    };
  }
  if (error instanceof Error) {
    return {
      errorCode: "console_client_error",
      message: error.message,
      requestId: null,
      details: null,
    };
  }
  return {
    errorCode: "unknown_error",
    message: "Unknown console API error.",
    requestId: null,
    details: null,
  };
}

function nativeHeaders(idempotencyKey?: string, scopeOverride?: Partial<ConsoleScope>, writeOptions: ConsoleWriteOptions = {}): HeadersInit {
  const scope = { ...readCurrentScope(), ...scopeOverride };
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": crypto.randomUUID(),
    "X-Tenant-Id": String(scope.tenant_id),
    "X-Project-Id": String(scope.project_id),
    "X-Environment": scope.environment,
  };
  const sessionToken = localStorage.getItem(TOKEN_KEY);
  if (sessionToken?.startsWith("sess_")) headers.Authorization = `Bearer ${sessionToken}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  if (writeOptions.auditReason?.trim()) headers["X-Audit-Reason"] = writeOptions.auditReason.trim();
  return headers;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function nativeClient(idempotencyKey?: string, scopeOverride?: Partial<ConsoleScope>, writeOptions: ConsoleWriteOptions = {}) {
  const baseUrl = apiBaseUrl();
  if (!baseUrl) {
    throw new Error("DimooRun API base URL is not configured.");
  }
  return withUnauthorizedHandling(createDimooRunClient({
    baseUrl,
    headers: nativeHeaders(idempotencyKey, scopeOverride, writeOptions),
  }));
}

function withUnauthorizedHandling<T extends Record<string, unknown>>(client: T): T {
  return new Proxy(client, {
    get(target, property, receiver) {
      const value = Reflect.get(target, property, receiver);
      if (typeof value !== "function") return value;
      return (...args: unknown[]) => {
        const result = value.apply(target, args);
        if (!result || typeof result.then !== "function") return result;
        return result.catch((error: unknown) => {
          handleUnauthorized(error);
          throw error;
        });
      };
    },
  });
}

function handleUnauthorized(error: unknown): void {
  if (!(error instanceof DimooRunApiError) || error.status !== 401) return;
  if (!localStorage.getItem(TOKEN_KEY)) return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(OPERATOR_KEY);
  localStorage.removeItem(SCOPE_KEY);
  window.dispatchEvent(new CustomEvent("dimoorun:auth-invalidated", { detail: error.errorCode }));
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign(`/login?redirect=${encodeURIComponent(current)}`);
  }
}

async function requestConsolePath<T>(
  path: string,
  init: RequestInit = {},
  scopeOverride?: Partial<ConsoleScope>,
  writeOptions: ConsoleWriteOptions = {},
): Promise<T> {
  const baseUrl = apiBaseUrl();
  if (!baseUrl) {
    throw new Error("DimooRun API base URL is not configured.");
  }
  const headers = {
    ...nativeHeaders(undefined, scopeOverride, writeOptions),
    ...(init.headers || {}),
  };
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      const body = await response.json() as { detail?: unknown };
      detail = body.detail ?? body;
    } catch {
      detail = { message: `HTTP ${response.status}` };
    }
    if (isRecord(detail)) {
      throw {
        status: response.status,
        errorCode: typeof detail.error_code === "string" ? detail.error_code : `http_${response.status}`,
        message: typeof detail.message === "string" ? detail.message : `HTTP ${response.status}`,
        requestId: typeof detail.request_id === "string" ? detail.request_id : null,
        details: isRecord(detail.details) ? detail.details : null,
      };
    }
    throw detail;
  }
  return await response.json() as T;
}

function mapNativeAgent(
  agent: NativeAgentRead,
  counts: { versionCount?: number; deploymentCount?: number } = {},
): Agent {
  return {
    id: agent.id,
    name: agent.name,
    description: agent.description,
    status: agent.status,
    createdAt: agent.created_at,
    versionCount: counts.versionCount ?? 0,
    deploymentCount: counts.deploymentCount ?? 0,
  };
}

function mapNativeAgentVersion(version: NativeAgentVersionRead): AgentVersion {
  return {
    id: version.id,
    agentId: version.agent_id,
    version: version.version,
    packageUri: version.package_uri,
    framework: version.framework,
    adapter: version.adapter,
    entrypoint: version.entrypoint,
    capabilities: version.capabilities,
    manifest: version.manifest,
    status: version.status,
  };
}

function mapNativeDeployment(deployment: NativeDeploymentRead): Deployment {
  const runtimeStatus =
    deployment.runtime_status === "failed" || deployment.runtime_status === "stopped"
      ? "degraded"
      : deployment.runtime_status === "not_loaded"
        ? "warming_up"
        : (deployment.runtime_status as Deployment["runtimeStatus"]);
  const desiredStatus =
    deployment.desired_status === "draft"
      ? "paused"
      : deployment.desired_status === "archived"
        ? "stopped"
        : (deployment.desired_status as Deployment["desiredStatus"]);
  return {
    id: deployment.id,
    agent: String(deployment.agent_id),
    environment: deployment.environment,
    version: String(deployment.agent_version_id),
    desiredStatus,
    runtimeStatus,
    instances: deployment.replicas,
    config: deployment.config ?? {},
    runningRuns: 0,
    queueBacklog: 0,
    worker: "native-worker",
    heartbeatAt: new Date().toISOString(),
    executionProfile: "default",
    modelGateway: "default",
  };
}

function mapNativeRun(run: NativeRunRead): Run {
  const status = run.status === "pending" ? "running" : run.status;
  return {
    id: run.id,
    agent: String(run.agent_id),
    framework: "LangGraph",
    adapter: "native",
    version: String(run.agent_version_id),
    actor: "api",
    status: ["succeeded", "failed", "running", "timeout", "cancelled"].includes(status)
      ? (status as Run["status"])
      : "running",
    createdAt: run.created_at,
    startedAt: run.started_at,
    finishedAt: run.finished_at,
    latencyMs: run.latency_ms,
    trigger: "api",
    deployment: run.deployment_id ? String(run.deployment_id) : "direct",
    traceId: run.thread_id || String(run.id),
    input: run.input,
    output: run.output,
    error: run.error,
  };
}

function mapNativeEvent(event: NativeEventRead): RuntimeEvent {
  return {
    runId: event.run_id,
    sequence: event.sequence,
    eventId: event.event_id,
    type: event.type,
    status: event.visibility_level,
    summary: `run ${event.run_id}: ${JSON.stringify(event.payload)}`,
    payload: event.payload,
  };
}

function mapConsoleDashboardSummary(summary: ConsoleDashboardSummaryRead): DashboardSummary {
  return {
    runCountToday: summary.run_count_today,
    successRate: summary.success_rate,
    p95LatencyMs: summary.p95_latency_ms,
    p99LatencyMs: summary.p99_latency_ms,
    queueBacklog: summary.queue_backlog,
    workerReady: summary.worker_ready,
    workerTotal: summary.worker_total,
    monthlyCostUsd: summary.monthly_cost_usd,
    pendingApprovals: summary.pending_approvals,
    runningRuns: summary.running_runs,
    activeIncidents: summary.active_incidents,
  };
}

function mapConsoleRuntimeOverview(overview: ConsoleRuntimeOverviewResponse): ConsoleRuntimeOverview {
  return {
    summary: mapConsoleDashboardSummary(overview.summary),
    recentFailures: overview.recent_failures.map((failure) => ({
      runId: failure.run_id,
      deploymentId: failure.deployment_id,
      agentId: failure.agent_id,
      agentVersionId: failure.agent_version_id,
      status: failure.status,
      errorSummary: failure.error_summary,
      createdAt: failure.created_at,
    })),
    pendingActions: overview.pending_actions.map((action) => ({
      resourceType: action.resource_type,
      resourceId: action.resource_id,
      action: action.action,
      label: action.label,
      disabledReason: action.disabled_reason,
      requiredPermissions: action.required_permissions,
      auditRequired: action.audit_required,
    })),
    trendPoints: overview.trend_points.map((point) => ({
      label: point.label,
      runs: point.runs,
      successRate: point.success_rate,
    })),
  };
}

function mapRuntimeMetricsSnapshot(snapshot: Record<string, unknown>): RuntimeMetricsSnapshot {
  const summary = isRecord(snapshot.summary) ? snapshot.summary : {};
  const queues = Array.isArray(snapshot.queues) ? snapshot.queues : [];
  const workers = Array.isArray(snapshot.workers) ? snapshot.workers : [];
  const activeIncidents = Array.isArray(snapshot.active_incidents) ? snapshot.active_incidents : [];
  const trendPoints = Array.isArray(snapshot.trend_points) ? snapshot.trend_points : [];
  return {
    summary: mapConsoleDashboardSummary(summary as ConsoleDashboardSummaryRead),
    queues: queues.map((item) => ({
      queue: String((item as Record<string, unknown>).queue || "default"),
      queueBacklog: Number((item as Record<string, unknown>).queue_backlog || 0),
      runningTasks: Number((item as Record<string, unknown>).running_tasks || 0),
      leasedTasks: Number((item as Record<string, unknown>).leased_tasks || 0),
      retryingTasks: Number((item as Record<string, unknown>).retrying_tasks || 0),
      deadLetters: Number((item as Record<string, unknown>).dead_letters || 0),
      oldestTaskAgeSeconds:
        typeof (item as Record<string, unknown>).oldest_task_age_seconds === "number"
          ? Number((item as Record<string, unknown>).oldest_task_age_seconds)
          : null,
    })),
    workers: workers.map((item) => ({
      workerId: String((item as Record<string, unknown>).worker_id || ""),
      heartbeatAgeSeconds:
        typeof (item as Record<string, unknown>).heartbeat_age_seconds === "number"
          ? Number((item as Record<string, unknown>).heartbeat_age_seconds)
          : null,
      readiness: String((item as Record<string, unknown>).readiness || "unknown"),
      liveness: String((item as Record<string, unknown>).liveness || "unknown"),
      activeAttempts: Number((item as Record<string, unknown>).active_attempts || 0),
      retryingTasks: Number((item as Record<string, unknown>).retrying_tasks || 0),
      deadLetterTasks: Number((item as Record<string, unknown>).dead_letter_tasks || 0),
    })),
    activeIncidents: activeIncidents.map((failure) => ({
      runId: Number((failure as Record<string, unknown>).run_id || 0),
      deploymentId: null,
      agentId: 0,
      agentVersionId: 0,
      status: String((failure as Record<string, unknown>).status || "failed"),
      errorSummary: String((failure as Record<string, unknown>).error_summary || "Run failed."),
      createdAt: String((failure as Record<string, unknown>).created_at || ""),
    })),
    trendPoints: trendPoints.map((point) => ({
      label: String((point as Record<string, unknown>).label || ""),
      runs: Number((point as Record<string, unknown>).runs || 0),
      successRate: Number((point as Record<string, unknown>).success_rate || 0),
    })),
  };
}

function mapPackageValidation(result: {
  status: string;
  ready: boolean;
  validation_token: string | null;
  errors: Array<{ field: string; code: string; message: string }>;
  warnings: string[];
  missing_secret_refs: string[];
  capabilities: Record<string, unknown>;
  next_action: string;
}): PackageValidationResult {
  return {
    status: result.status,
    ready: result.ready,
    validationToken: result.validation_token,
    errors: result.errors,
    warnings: result.warnings,
    missingSecretRefs: result.missing_secret_refs,
    capabilities: result.capabilities,
    nextAction: result.next_action,
  };
}

function mapDeploymentPromotionPreview(result: DeploymentPromotionPreviewRead): DeploymentPromotionPreview {
  return {
    deploymentId: result.deployment_id,
    environment: result.environment,
    desiredStatus: result.desired_status,
    runtimeStatus: result.runtime_status,
    currentAgentVersionId: result.current_agent_version_id,
    candidateAgentVersionId: result.candidate_agent_version_id,
    activeRuns: result.active_runs,
    queuedTasks: result.queued_tasks,
    candidateValidationStatus: result.candidate_validation_status,
    rollbackAgentVersionId: result.rollback_agent_version_id,
    requiredPermissions: result.required_permissions,
    auditRequired: result.audit_required,
    canPromote: result.can_promote,
    blockedReason: result.blocked_reason,
    warnings: result.warnings,
  };
}

function mapReplayComparison(result: ReplayComparisonRead): ReplayComparison {
  return {
    comparisonId: result.comparison_id,
    sourceRun: mapNativeRun(result.source_run),
    replayRun: mapNativeRun(result.replay_run),
    sourceEvents: result.source_events.map(mapNativeEvent),
    replayEvents: result.replay_events.map(mapNativeEvent),
    inputDiff: result.input_diff,
    outputDiff: result.output_diff,
    errorDiff: result.error_diff,
    eventDiff: {
      changed: result.event_diff.changed,
      sourceCount: result.event_diff.source_count,
      replayCount: result.event_diff.replay_count,
      addedTypes: result.event_diff.added_types,
      removedTypes: result.event_diff.removed_types,
    },
    latencyDeltaMs: result.latency_delta_ms,
    costDeltaUsd: result.cost_delta_usd,
    regressionSignal: result.regression_signal,
    provenance: result.provenance,
  };
}

function mapDatasetCapture(result: {
  capture_id: string;
  comparison_id: string;
  dataset_name: string;
  label: string | null;
  source_run_id: ResourceId;
  replay_run_id: ResourceId;
  provenance: Record<string, unknown>;
}): DatasetCapture {
  return {
    captureId: result.capture_id,
    comparisonId: result.comparison_id,
    datasetName: result.dataset_name,
    label: result.label,
    sourceRunId: result.source_run_id,
    replayRunId: result.replay_run_id,
    provenance: result.provenance,
  };
}

function mapRunDatasetCapture(result: Record<string, unknown>): RunDatasetCapture {
  return {
    datasetId: Number(result.dataset_id || 0),
    datasetName: String(result.dataset_name || ""),
    datasetItemId: Number(result.dataset_item_id || 0),
    sourceRunId: Number(result.source_run_id || 0),
    label: typeof result.label === "string" ? result.label : null,
    payloadPreview: isRecord(result.payload_preview) ? result.payload_preview : {},
    redaction: isRecord(result.redaction) ? result.redaction : {},
    provenance: isRecord(result.provenance) ? result.provenance : {},
    audit: isRecord(result.audit) ? result.audit : {},
    duplicate: result.duplicate === true,
  };
}

function mapExperimentRunResult(result: Record<string, unknown>): ExperimentRunResult {
  return {
    experiment: isRecord(result.experiment) ? result.experiment : {},
    run: isRecord(result.run) ? result.run : {},
    results: Array.isArray(result.results) ? result.results.filter(isRecord) : [],
    scoreDistribution: isRecord(result.score_distribution) ? result.score_distribution : {},
    qualityGate: isRecord(result.quality_gate) ? result.quality_gate : {},
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapQualityGatePreview(result: Record<string, unknown>): QualityGatePreview {
  return {
    status: String(result.status || "unknown"),
    promotionAllowed: result.promotion_allowed === true,
    blockedReason: typeof result.blocked_reason === "string" ? result.blocked_reason : null,
    requiredEvidence: Array.isArray(result.required_evidence)
      ? result.required_evidence.map(String)
      : [],
    evidence: isRecord(result.evidence) ? result.evidence : {},
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapIncidentWorkflow(result: Record<string, unknown>): IncidentWorkflowResult {
  return {
    incident: isRecord(result.incident) ? result.incident : {},
    timeline: Array.isArray(result.timeline) ? result.timeline.filter(isRecord) : [],
    linkedEvidence: isRecord(result.linked_evidence) ? result.linked_evidence : {},
    deliveryAttempts: Array.isArray(result.delivery_attempts) ? result.delivery_attempts.filter(isRecord) : [],
    resolution: isRecord(result.resolution) ? result.resolution : null,
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapNotificationTest(result: Record<string, unknown>): NotificationTestResult {
  return {
    status: String(result.status || "unknown"),
    deliveryAttempt: isRecord(result.delivery_attempt) ? result.delivery_attempt : {},
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapBackupDryRun(result: Record<string, unknown>): BackupDryRunResult {
  return {
    status: String(result.status || "unknown"),
    scopeProof: isRecord(result.scope_proof) ? result.scope_proof : {},
    validation: isRecord(result.validation) ? result.validation : {},
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapRestoreDryRun(result: Record<string, unknown>): RestoreDryRunResult {
  return {
    ...mapBackupDryRun(result),
    backupRef: typeof result.backup_ref === "string" ? result.backup_ref : null,
  };
}

function mapPublishValidation(result: Record<string, unknown>): PublishValidationResult {
  return {
    status: String(result.status || "unknown"),
    canPublish: result.can_publish === true,
    checks: isRecord(result.checks) ? Object.fromEntries(
      Object.entries(result.checks).filter((entry): entry is [string, Record<string, unknown>] => isRecord(entry[1])),
    ) : {},
    blockedReasons: Array.isArray(result.blocked_reasons) ? result.blocked_reasons.map(String) : [],
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapPublishedSurfacePublish(result: Record<string, unknown>): PublishedSurfacePublishResult {
  return {
    ...mapPublishValidation(result),
    surface: isRecord(result.surface) ? result.surface : {},
    rollout: isRecord(result.rollout) ? result.rollout : {},
  };
}

function mapIngressRouteTest(result: Record<string, unknown>): IngressRouteTestResult {
  return {
    status: String(result.status || "unknown"),
    matchedDeployment: isRecord(result.matched_deployment) ? result.matched_deployment : {},
    authDecision: isRecord(result.auth_decision) ? result.auth_decision : {},
    policyDecision: isRecord(result.policy_decision) ? result.policy_decision : {},
    expectedRuntimeTask: isRecord(result.expected_runtime_task) ? result.expected_runtime_task : {},
    blockedReasons: Array.isArray(result.blocked_reasons) ? result.blocked_reasons.map(String) : [],
    requestLog: isRecord(result.request_log) ? result.request_log : {},
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapPublishedSurfaceDetail(result: Record<string, unknown>): PublishedSurfaceDetail {
  return {
    surface: isRecord(result.surface) ? result.surface : {},
    deploymentBindingHealth: isRecord(result.deployment_binding_health) ? result.deployment_binding_health : {},
    exposureHealth: isRecord(result.exposure_health) ? result.exposure_health : {},
    requestLogs: Array.isArray(result.request_logs) ? result.request_logs.filter(isRecord) : [],
    rolloutHistory: Array.isArray(result.rollout_history) ? result.rollout_history.filter(isRecord) : [],
    actions: isRecord(result.actions) ? result.actions : {},
  };
}

function mapPublishedSurfaceRollout(result: Record<string, unknown>): PublishedSurfaceRolloutResult {
  return {
    surface: isRecord(result.surface) ? result.surface : {},
    rollout: isRecord(result.rollout) ? result.rollout : {},
    rolloutHistory: Array.isArray(result.rollout_history) ? result.rollout_history.filter(isRecord) : [],
    audit: isRecord(result.audit) ? result.audit : {},
  };
}

function mapNativeRunAttempt(attempt: Record<string, unknown>): RunAttempt {
  return {
    id: Number(attempt.id),
    runId: Number(attempt.run_id),
    taskId: attempt.task_id === null || attempt.task_id === undefined ? null : Number(attempt.task_id),
    attemptNo: Number(attempt.attempt_no),
    workerId: attempt.worker_id === null || attempt.worker_id === undefined ? null : String(attempt.worker_id),
    status: String(attempt.status || "unknown"),
    error: attempt.error === null || attempt.error === undefined ? null : String(attempt.error),
  };
}

function mapNativeTask(task: NativeTaskRead): Task {
  return {
    id: task.id,
    runId: task.run_id,
    status: ["queued", "leased", "running", "retrying", "dead_letter", "succeeded", "cancelled"].includes(task.status)
      ? (task.status as Task["status"])
      : "queued",
    attempt: task.attempt,
    queue: task.queue,
    workerId: "native-worker",
    heartbeatAt: "",
    leaseUntil: "",
    fencingToken: 0,
    retryCount: Math.max(0, task.attempt - 1),
    deadLetterReason: task.dead_letter_reason || undefined,
    partitionKey: task.partition_key || undefined,
    resourceClass: task.resource_class || undefined,
    quotaBlockingReason: task.quota_blocking_reason as Task["quotaBlockingReason"],
  };
}

function mapAdminHumanTask(item: AdminResource): HumanTask {
  const status = typeof item.status === "string" ? item.status : "pending";
  const risk = typeof item.risk === "string" ? item.risk : "medium";
  const decision = isRecord(item.decision) ? item.decision : {};
  const resumeOutcome = isRecord(item.resume_outcome) ? item.resume_outcome : {};
  return {
    id: item.id,
    source: String(item.source || item.name || "admin"),
    risk: ["medium", "high", "critical"].includes(risk) ? (risk as HumanTask["risk"]) : "medium",
    status: ["pending", "approved", "rejected"].includes(status)
      ? (status as HumanTask["status"])
      : "pending",
    assignee: String(item.assignee || "unassigned"),
    requester: String(item.requester || "unknown"),
    riskReason: String(item.risk_reason || ""),
    decisionContext: isRecord(item.decision_context) ? item.decision_context : {},
    diff: isRecord(item.diff) ? item.diff : {},
    decision: {
      comment: typeof decision.comment === "string" ? decision.comment : null,
      decidedBy: typeof decision.decided_by === "string" ? decision.decided_by : null,
    },
    resumeOutcome: {
      status: String(resumeOutcome.status || (status === "pending" ? "waiting" : "resumed")),
      taskId: Number(resumeOutcome.task_id || item.id),
      decision: typeof resumeOutcome.decision === "string" ? resumeOutcome.decision : undefined,
    },
    expiresAt: String(item.expires_at || item.expiresAt || ""),
  };
}

function mapPolicySimulation(result: Record<string, unknown>): PolicySimulation {
  const decision = isRecord(result.decision) ? result.decision : {};
  const resources = Array.isArray(result.matched_resources) ? result.matched_resources : [];
  return {
    decision: {
      result: String(decision.result || "allow"),
      policyId: decision.policy_id === null || decision.policy_id === undefined ? null : Number(decision.policy_id),
      policyName: typeof decision.policy_name === "string" ? decision.policy_name : null,
      reason: typeof decision.reason === "string" ? decision.reason : null,
    },
    matchedResources: resources.filter(isRecord).map((resource) => ({
      resourceType: String(resource.resource_type || ""),
      resourceId: resource.resource_id === null || resource.resource_id === undefined ? null : Number(resource.resource_id),
      action: String(resource.action || ""),
      environment: typeof resource.environment === "string" ? resource.environment : null,
    })),
    auditPreview: isRecord(result.audit_preview) ? result.audit_preview : {},
    conflictWarnings: Array.isArray(result.conflict_warnings)
      ? result.conflict_warnings.filter(isRecord)
      : [],
  };
}

function mapPolicyActivation(result: Record<string, unknown>): PolicyActivation {
  const rollbackTarget = isRecord(result.rollback_target) ? result.rollback_target : {};
  const comparison = isRecord(result.comparison) ? result.comparison : {};
  const changedFields = Array.isArray(comparison.changed_fields) ? comparison.changed_fields : [];
  return {
    item: isRecord(result.item) ? result.item : {},
    version: Number(result.version || 0),
    comparison: {
      fromVersion:
        comparison.from_version === null || comparison.from_version === undefined
          ? null
          : Number(comparison.from_version),
      toVersion: Number(comparison.to_version || result.version || 0),
      changedFields: changedFields.filter(isRecord).map((field) => ({
        field: String(field.field || ""),
        before: field.before,
        after: field.after,
      })),
    },
    audit: isRecord(result.audit) ? result.audit : {},
    rollbackTarget: {
      policyId: Number(rollbackTarget.policy_id || 0),
      version: Number(rollbackTarget.version || 0),
    },
    conflictWarnings: Array.isArray(result.conflict_warnings)
      ? result.conflict_warnings.filter(isRecord)
      : [],
  };
}

function mapModelGatewayTest(result: Record<string, unknown>): ModelGatewayTestResult {
  return {
    credentialValidation: isRecord(result.credential_validation) ? result.credential_validation : {},
    safeHealthProbe: isRecord(result.safe_health_probe) ? result.safe_health_probe : {},
    budgetPreview: isRecord(result.budget_preview) ? result.budget_preview : {},
    fallbackPreview: isRecord(result.fallback_preview) ? result.fallback_preview : {},
    providerErrorNormalization: isRecord(result.provider_error_normalization) ? result.provider_error_normalization : {},
    auditPreview: isRecord(result.audit_preview) ? result.audit_preview : {},
  };
}

function mapToolDryRun(result: Record<string, unknown>): ToolDryRunResult {
  return {
    schemaValidation: isRecord(result.schema_validation) ? result.schema_validation : {},
    riskClassification: isRecord(result.risk_classification) ? result.risk_classification : {},
    policyPreview: isRecord(result.policy_preview) ? result.policy_preview : {},
    approvalRequirement: isRecord(result.approval_requirement) ? result.approval_requirement : {},
    usageHistoryLink: String(result.usage_history_link || ""),
    auditPreview: isRecord(result.audit_preview) ? result.audit_preview : {},
  };
}

function mapSecretValidation(result: Record<string, unknown>): SecretValidationResult {
  return {
    validation: isRecord(result.validation) ? result.validation : {},
    secretValue: null,
    lastUsed: isRecord(result.last_used) ? result.last_used : {},
    accessAudit: isRecord(result.access_audit) ? result.access_audit : {},
  };
}

function mapSecretRotation(result: Record<string, unknown>): SecretRotationResult {
  return {
    rotation: isRecord(result.rotation) ? result.rotation : {},
    lastUsed: isRecord(result.last_used) ? result.last_used : {},
    accessAudit: isRecord(result.access_audit) ? result.access_audit : {},
  };
}

function mapRuntimeControlAction(action: Record<string, unknown>): RuntimeControlAction {
  return {
    action: String(action.action || ""),
    label: String(action.label || action.action || ""),
    available: action.available === true,
    disabledReasons: Array.isArray(action.disabled_reasons)
      ? action.disabled_reasons.map(String)
      : [],
    requiredPermissions: Array.isArray(action.required_permissions)
      ? action.required_permissions.map(String)
      : [],
    auditRequired: action.audit_required === true,
  };
}

function mapRuntimeWorker(worker: Record<string, unknown>): RuntimeWorker {
  return {
    workerId: String(worker.worker_id || ""),
    environment: String(worker.environment || ""),
    status: String(worker.status || "unknown"),
    drainStatus: String(worker.drain_status || "active"),
    version: String(worker.version || "unknown"),
    queues: Array.isArray(worker.queues) ? worker.queues.map(String) : [],
    capacity: Number(worker.capacity || 0),
    activeAttempts: Number(worker.active_attempts || 0),
    activeRuns: Number(worker.active_runs || 0),
    heartbeatAgeSeconds: typeof worker.heartbeat_age_seconds === "number"
      ? worker.heartbeat_age_seconds
      : null,
    lastError: typeof worker.last_error === "string" ? worker.last_error : null,
    liveness: String(worker.liveness || "offline"),
    readiness: String(worker.readiness || "degraded"),
    retryingTasks: Number(worker.retrying_tasks || 0),
    deadLetterTasks: Number(worker.dead_letter_tasks || 0),
    deploymentIds: Array.isArray(worker.deployment_ids) ? worker.deployment_ids.map(Number) : [],
    restartRequestedAt: typeof worker.restart_requested_at === "string"
      ? worker.restart_requested_at
      : null,
  };
}

function mapRuntimeWorkerDetail(item: Record<string, unknown>): RuntimeWorkerDetail {
  return {
    ...mapRuntimeWorker(item),
    activeTaskIds: Array.isArray(item.active_task_ids) ? item.active_task_ids.map(Number) : [],
    activeRunIds: Array.isArray(item.active_run_ids) ? item.active_run_ids.map(Number) : [],
    actions: Array.isArray(item.actions)
      ? item.actions.filter(isRecord).map(mapRuntimeControlAction)
      : [],
  };
}

function mapRuntimeAgentInstance(item: Record<string, unknown>): RuntimeAgentInstance {
  return {
    id: Number(item.id || 0),
    deploymentId: Number(item.deployment_id || 0),
    environment: String(item.environment || ""),
    agentId: Number(item.agent_id || 0),
    agentVersionId: Number(item.agent_version_id || 0),
    workerId: String(item.worker_id || ""),
    status: String(item.status || "unknown"),
    activeRuns: Number(item.active_runs || 0),
    recentFailures: Number(item.recent_failures || 0),
    concurrencyLimit: Number(item.concurrency_limit || 0),
    runtimeConfigHash: String(item.runtime_config_hash || ""),
    executionProfileId: typeof item.execution_profile_id === "string"
      ? item.execution_profile_id
      : null,
    cacheKey: String(item.cache_key || ""),
    loadedAt: typeof item.loaded_at === "string" ? item.loaded_at : null,
    heartbeatAt: typeof item.heartbeat_at === "string" ? item.heartbeat_at : null,
    lastError: typeof item.last_error === "string" ? item.last_error : null,
  };
}

function mapRuntimeAgentInstanceDetail(
  item: Record<string, unknown>,
): RuntimeAgentInstanceDetail {
  return {
    ...mapRuntimeAgentInstance(item),
    deploymentDesiredStatus: String(item.deployment_desired_status || ""),
    deploymentRuntimeStatus: String(item.deployment_runtime_status || ""),
  };
}

function mapRuntimeQueuePressure(item: Record<string, unknown>): RuntimeQueuePressure {
  return {
    queue: String(item.queue || ""),
    queueBacklog: Number(item.queue_backlog || 0),
    leased: Number(item.leased || 0),
    running: Number(item.running || 0),
    retrying: Number(item.retrying || 0),
    deadLetter: Number(item.dead_letter || 0),
    oldestTaskAgeSeconds: typeof item.oldest_task_age_seconds === "number"
      ? item.oldest_task_age_seconds
      : null,
  };
}

function mapRuntimeCapacitySummary(item: Record<string, unknown>): RuntimeCapacitySummary {
  return {
    queueBacklog: Number(item.queue_backlog || 0),
    activeAttempts: Number(item.active_attempts || 0),
    totalCapacity: Number(item.total_capacity || 0),
    saturationRatio: Number(item.saturation_ratio || 0),
    timeToDrainSeconds: Number(item.time_to_drain_seconds || 0),
    retryPressure: Number(item.retry_pressure || 0),
    deadLetterPressure: Number(item.dead_letter_pressure || 0),
    recommendedAction: String(item.recommended_action || "steady_state"),
    recommendedReason: String(item.recommended_reason || ""),
    activeWorkers: Number(item.active_workers || 0),
    drainingWorkers: Number(item.draining_workers || 0),
    quarantinedWorkers: Number(item.quarantined_workers || 0),
    criticalAttempts: Number(item.critical_attempts || 0),
    queues: Array.isArray(item.queues) ? item.queues.filter(isRecord).map(mapRuntimeQueuePressure) : [],
  };
}

function mapCompatibilityExplorerResult(result: Record<string, unknown>): CompatibilityExplorerResult {
  return {
    operation: String(result.operation || "unknown"),
    compatResponse: isRecord(result.compat_response) ? result.compat_response : {},
    nativeResources: isRecord(result.native_resources) ? result.native_resources : {},
    resourceLinks: Array.isArray(result.resource_links)
      ? result.resource_links.filter(isRecord).map((item) => ({
        label: String(item.label || ""),
        path: String(item.path || ""),
      }))
      : [],
    unsupportedCapabilityExplanations: Array.isArray(result.unsupported_capability_explanations)
      ? result.unsupported_capability_explanations.filter(isRecord)
      : [],
    divergenceReason: typeof result.divergence_reason === "string" ? result.divergence_reason : null,
    goldenRecord: isRecord(result.golden_record) ? result.golden_record : {},
    streamEvents: Array.isArray(result.stream_events) ? result.stream_events.filter(isRecord) : undefined,
    streamStatus: isRecord(result.stream_status) ? result.stream_status : undefined,
  };
}

function mapCompatibilityMigrationResponse(result: Record<string, unknown>): CompatibilityMigrationResponse {
  const report = isRecord(result.report) ? result.report : {};
  return {
    report: {
      framework: String(report.framework || "langgraph"),
      adapter: String(report.adapter || "langgraph"),
      overallStatus: String(report.overall_status || "unknown"),
      blockedReason: typeof report.blocked_reason === "string" ? report.blocked_reason : null,
      unsupportedCapabilities: Array.isArray(report.unsupported_capabilities)
        ? report.unsupported_capabilities.filter(isRecord)
        : [],
      requiredDimooRunConfig: Array.isArray(report.required_dimoorun_config)
        ? report.required_dimoorun_config.map(String)
        : [],
      adapterContractVersion: String(report.adapter_contract_version || ""),
      checkpointRequirements: isRecord(report.checkpoint_requirements) ? report.checkpoint_requirements : {},
      streamingSupport: isRecord(report.streaming_support) ? report.streaming_support : {},
      governanceImplications: Array.isArray(report.governance_implications)
        ? report.governance_implications.map(String)
        : [],
      recommendedActions: Array.isArray(report.recommended_actions)
        ? report.recommended_actions.map(String)
        : [],
    },
    goldenRecord: isRecord(result.golden_record) ? result.golden_record : {},
    requestId: typeof result.request_id === "string" ? result.request_id : null,
  };
}

export const liveConsoleClient = {
  async login(email: string, password: string): Promise<ConsoleLogin> {
    return nativeClient().login(email, password);
  },
  async me(): Promise<ConsoleOperator> {
    return (await nativeClient().me()).operator;
  },
  async logout() {
    return nativeClient().logout();
  },
  async changePassword(currentPassword: string, newPassword: string) {
    return nativeClient(crypto.randomUUID()).changePassword(currentPassword, newPassword);
  },
  async getDashboardSummary(): Promise<DashboardSummary> {
    return mapConsoleDashboardSummary(await nativeClient().getConsoleDashboardSummary());
  },
  async getRuntimeOverview(): Promise<ConsoleRuntimeOverview> {
    return mapConsoleRuntimeOverview(
      await requestConsolePath<ConsoleRuntimeOverviewResponse>("/v1/console/runtime-overview"),
    );
  },
  async getRuntimeMetricsSummary(): Promise<RuntimeMetricsSnapshot> {
    return mapRuntimeMetricsSnapshot(
      await requestConsolePath<Record<string, unknown>>("/v1/runtime/metrics/summary"),
    );
  },
  async listRuntimeWorkers(): Promise<CursorPage<RuntimeWorker>> {
    const payload = await requestConsolePath<{
      items: Array<Record<string, unknown>>;
      count: number;
      request_id: string | null;
    }>("/v1/console/workers");
    return page(payload.items.map(mapRuntimeWorker));
  },
  async getRuntimeWorker(workerId: string): Promise<RuntimeWorkerDetail> {
    const payload = await requestConsolePath<{
      item: Record<string, unknown>;
      request_id: string | null;
    }>(`/v1/console/workers/${encodeURIComponent(workerId)}`);
    return mapRuntimeWorkerDetail(payload.item);
  },
  async controlRuntimeWorker(
    workerId: string,
    action: string,
    options: ConsoleWriteOptions = {},
  ): Promise<RuntimeWorkerDetail> {
    const payload = await requestConsolePath<{
      item: Record<string, unknown>;
      request_id: string | null;
    }>(
      `/v1/console/workers/${encodeURIComponent(workerId)}/${encodeURIComponent(action)}`,
      { method: "POST" },
      undefined,
      options,
    );
    return mapRuntimeWorkerDetail(payload.item);
  },
  async getRuntimeCapacitySummary(): Promise<RuntimeCapacitySummary> {
    const payload = await requestConsolePath<{
      item: Record<string, unknown>;
      request_id: string | null;
    }>("/v1/console/capacity");
    return mapRuntimeCapacitySummary(payload.item);
  },
  async listRuntimeAgentInstances(): Promise<CursorPage<RuntimeAgentInstance>> {
    const payload = await requestConsolePath<{
      items: Array<Record<string, unknown>>;
      count: number;
      request_id: string | null;
    }>("/v1/console/agent-instances");
    return page(payload.items.map(mapRuntimeAgentInstance));
  },
  async getRuntimeAgentInstance(instanceId: ResourceId): Promise<RuntimeAgentInstanceDetail> {
    const payload = await requestConsolePath<{
      item: Record<string, unknown>;
      request_id: string | null;
    }>(`/v1/console/agent-instances/${instanceId}`);
    return mapRuntimeAgentInstanceDetail(payload.item);
  },
  async validatePackage(payload: PackageValidationPayload): Promise<PackageValidationResult> {
    return mapPackageValidation(await nativeClient(crypto.randomUUID()).validatePackage(payload));
  },
  async listAgents(): Promise<CursorPage<Agent>> {
    const client = nativeClient();
    const [agents, deployments] = await Promise.all([
      client.listAgents(),
      client.listDeployments(),
    ]);
    const versionsByAgent = await Promise.all(
      agents.map(async (agent) => [agent.id, await client.listAgentVersions(agent.id)] as const),
    );
    const versionCounts = new Map(
      versionsByAgent.map(([agentId, versions]) => [agentId, versions.length]),
    );
    const deploymentCounts = deployments.reduce((counts, deployment) => {
      counts.set(deployment.agent_id, (counts.get(deployment.agent_id) ?? 0) + 1);
      return counts;
    }, new Map<ResourceId, number>());
    return page(
      agents.map((agent) =>
        mapNativeAgent(agent, {
          versionCount: versionCounts.get(agent.id) ?? 0,
          deploymentCount: deploymentCounts.get(agent.id) ?? 0,
        }),
      ),
    );
  },
  async createAgent(payload: Record<string, unknown>): Promise<Agent> {
    const created = await nativeClient(crypto.randomUUID()).createAgent(payload);
    return mapNativeAgent(created);
  },
  async updateAgent(agentId: ResourceId, payload: Record<string, unknown>): Promise<Agent> {
    const updated = await nativeClient(crypto.randomUUID()).updateAgent(agentId, payload);
    return mapNativeAgent(updated);
  },
  async archiveAgent(agentId: ResourceId): Promise<Agent> {
    const archived = await nativeClient(crypto.randomUUID()).archiveAgent(agentId);
    return mapNativeAgent(archived);
  },
  async listAgentVersions(agentId: ResourceId): Promise<CursorPage<AgentVersion>> {
    const payload = await nativeClient().listAgentVersions(agentId);
    return page(payload.map(mapNativeAgentVersion));
  },
  async createAgentVersion(agentId: ResourceId, payload: Record<string, unknown>): Promise<AgentVersion> {
    const created = await nativeClient(crypto.randomUUID()).createAgentVersion(agentId, payload);
    return mapNativeAgentVersion(created);
  },
  async updateAgentVersion(agentId: ResourceId, version: string, payload: Record<string, unknown>): Promise<AgentVersion> {
    const updated = await nativeClient(crypto.randomUUID()).updateAgentVersion(agentId, version, payload);
    return mapNativeAgentVersion(updated);
  },
  async archiveAgentVersion(agentId: ResourceId, version: string): Promise<AgentVersion> {
    const archived = await nativeClient(crypto.randomUUID()).archiveAgentVersion(agentId, version);
    return mapNativeAgentVersion(archived);
  },
  async listDeployments(): Promise<CursorPage<Deployment>> {
    const payload = await nativeClient().listDeployments();
    return page(payload.map(mapNativeDeployment));
  },
  async createDeployment(payload: NativeDeploymentCreatePayload, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const created = await nativeClient(crypto.randomUUID(), undefined, options).createDeployment(payload);
    return mapNativeDeployment(created);
  },
  async updateDeployment(deploymentId: ResourceId, payload: NativeDeploymentUpdatePayload, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const updated = await nativeClient(crypto.randomUUID(), undefined, options).updateDeployment(deploymentId, payload);
    return mapNativeDeployment(updated);
  },
  async archiveDeployment(deploymentId: ResourceId, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const archived = await nativeClient(crypto.randomUUID(), undefined, options).archiveDeployment(deploymentId);
    return mapNativeDeployment(archived);
  },
  async controlDeployment(deploymentId: ResourceId, operation: string, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const payload = await nativeClient(crypto.randomUUID(), undefined, options).controlDeployment(deploymentId, operation);
    return mapNativeDeployment(payload);
  },
  async getDeploymentPromotionPreview(deploymentId: ResourceId, candidateVersionId: ResourceId): Promise<DeploymentPromotionPreview> {
    return mapDeploymentPromotionPreview(
      await nativeClient().getDeploymentPromotionPreview(deploymentId, candidateVersionId),
    );
  },
  async promoteDeployment(deploymentId: ResourceId, payload: DeploymentPromotePayload, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const promoted = await nativeClient(crypto.randomUUID(), undefined, options).promoteDeployment(deploymentId, payload);
    return mapNativeDeployment(promoted);
  },
  async rollbackDeployment(deploymentId: ResourceId, payload: DeploymentRollbackPayload, options: ConsoleWriteOptions = {}): Promise<Deployment> {
    const rolledBack = await nativeClient(crypto.randomUUID(), undefined, options).rollbackDeployment(deploymentId, payload);
    return mapNativeDeployment(rolledBack);
  },
  async createDeploymentTask(deploymentId: ResourceId, payload: NativeDeploymentTaskCreatePayload, options: ConsoleWriteOptions = {}): Promise<TaskCreateResult> {
    const response = await nativeClient(undefined, undefined, options).createDeploymentTask(
      deploymentId,
      payload,
      crypto.randomUUID(),
    );
    return {
      runId: response.run_id,
      taskId: response.task_id,
      status: response.status,
      replayed: response.replayed,
    };
  },
  async listRuns(): Promise<CursorPage<Run>> {
    const payload = await nativeClient().listRuns();
    return page(payload.map(mapNativeRun));
  },
  async getRun(runId: ResourceId): Promise<Run | null> {
    const payload = await nativeClient().getRun(runId);
    return mapNativeRun(payload);
  },
  async controlRun(runId: ResourceId, operation: string): Promise<Run> {
    const payload = await nativeClient(crypto.randomUUID()).controlRun(runId, operation);
    return mapNativeRun(payload);
  },
  async replayRun(runId: ResourceId, agentVersionId?: ResourceId | null): Promise<Run> {
    const payload = await nativeClient(crypto.randomUUID()).replayRun(runId, {
      agent_version_id: agentVersionId ?? undefined,
    });
    return mapNativeRun(payload);
  },
  async createReplayComparison(payload: ReplayComparisonRequest, options: ConsoleWriteOptions = {}): Promise<ReplayComparison> {
    return mapReplayComparison(
      await nativeClient(crypto.randomUUID(), undefined, options).createReplayComparison(payload),
    );
  },
  async captureReplayDataset(comparisonId: string, payload: DatasetCapturePayload, options: ConsoleWriteOptions = {}): Promise<DatasetCapture> {
    return mapDatasetCapture(
      await nativeClient(crypto.randomUUID(), undefined, options).captureReplayDataset(comparisonId, payload),
    );
  },
  async captureRunDataset(payload: Record<string, unknown>): Promise<RunDatasetCapture> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/datasets/capture-run",
      payload,
    );
    return mapRunDatasetCapture(response as Record<string, unknown>);
  },
  async runExperiment(payload: Record<string, unknown>): Promise<ExperimentRunResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/experiments/run",
      payload,
    );
    return mapExperimentRunResult(response as Record<string, unknown>);
  },
  async previewQualityGate(payload: Record<string, unknown>): Promise<QualityGatePreview> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/quality-gates/preview",
      payload,
    );
    return mapQualityGatePreview(response as Record<string, unknown>);
  },
  async acknowledgeIncident(incidentId: ResourceId, payload: Record<string, unknown>): Promise<IncidentWorkflowResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/incidents/${incidentId}/acknowledge`,
      payload,
    );
    return mapIncidentWorkflow(response as Record<string, unknown>);
  },
  async resolveIncident(incidentId: ResourceId, payload: Record<string, unknown>): Promise<IncidentWorkflowResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/incidents/${incidentId}/resolve`,
      payload,
    );
    return mapIncidentWorkflow(response as Record<string, unknown>);
  },
  async testNotification(payload: Record<string, unknown>): Promise<NotificationTestResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/notifications/test-send",
      payload,
    );
    return mapNotificationTest(response as Record<string, unknown>);
  },
  async previewBackup(payload: Record<string, unknown>): Promise<BackupDryRunResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/backups/dry-run",
      payload,
    );
    return mapBackupDryRun(response as Record<string, unknown>);
  },
  async previewRestore(payload: Record<string, unknown>): Promise<RestoreDryRunResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/backups/restore-dry-run",
      payload,
    );
    return mapRestoreDryRun(response as Record<string, unknown>);
  },
  async validatePublishedSurface(payload: Record<string, unknown>): Promise<PublishValidationResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/published-surfaces/validate",
      payload,
    );
    return mapPublishValidation(response as Record<string, unknown>);
  },
  async publishSurface(payload: Record<string, unknown>): Promise<PublishedSurfacePublishResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/published-surfaces/publish",
      payload,
    );
    return mapPublishedSurfacePublish(response as Record<string, unknown>);
  },
  async testIngressRoute(payload: Record<string, unknown>): Promise<IngressRouteTestResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/ingress-routes/test",
      payload,
    );
    return mapIngressRouteTest(response as Record<string, unknown>);
  },
  async getPublishedSurfaceDetail(surfaceId: ResourceId): Promise<PublishedSurfaceDetail> {
    const payload = await nativeClient().listAdminCollection<Record<string, unknown>>(
      `/v1/console/published-surfaces/${surfaceId}`,
    ) as unknown as Record<string, unknown>;
    return mapPublishedSurfaceDetail(payload);
  },
  async rolloutPublishedSurface(surfaceId: ResourceId, payload: Record<string, unknown>): Promise<PublishedSurfaceRolloutResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/published-surfaces/${surfaceId}/rollout`,
      payload,
    );
    return mapPublishedSurfaceRollout(response as Record<string, unknown>);
  },
  async createTask(agentId: ResourceId, payload: NativeTaskCreatePayload): Promise<TaskCreateResult> {
    const response = await nativeClient(crypto.randomUUID()).createTask(
      agentId,
      payload,
      crypto.randomUUID(),
    );
    return {
      runId: response.run_id,
      taskId: response.task_id,
      status: response.status,
      replayed: response.replayed,
    };
  },
  async listRunEvents(runId: ResourceId): Promise<CursorPage<RuntimeEvent>> {
    const payload = await nativeClient().listRunEvents(runId);
    return page(payload.map(mapNativeEvent));
  },
  async listRunAttempts(runId: ResourceId): Promise<CursorPage<RunAttempt>> {
    const payload = await nativeClient().listRunAttempts(runId);
    return page(payload.map(mapNativeRunAttempt));
  },
  async listTasks(): Promise<CursorPage<Task>> {
    const payload = await nativeClient().listTasks();
    return page(payload.map(mapNativeTask));
  },
  async cancelTask(taskId: ResourceId): Promise<Task> {
    const payload = await nativeClient(crypto.randomUUID()).cancelTask(taskId);
    return mapNativeTask(payload as NativeTaskRead);
  },
  async listEvents(): Promise<CursorPage<RuntimeEvent>> {
    const payload = await nativeClient().listEvents();
    return page(payload.map(mapNativeEvent));
  },
  async listHumanTasks(): Promise<CursorPage<HumanTask>> {
    const payload = await nativeClient().listAdminCollection<AdminResource>("/v1/human-tasks");
    return page(payload.items.map(mapAdminHumanTask));
  },
  async listCompatibilityAssistants(): Promise<CursorPage<CompatibilityExplorerResult>> {
    const payload = await nativeClient().listAdminCollection<Record<string, unknown>>(
      "/v1/console/compatibility/langgraph/assistants",
    );
    return page(payload.items.map((item) => mapCompatibilityExplorerResult(item as Record<string, unknown>)));
  },
  async createCompatibilityAssistant(payload: Record<string, unknown>): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/console/compatibility/langgraph/assistants",
      payload,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async createCompatibilityThread(payload: Record<string, unknown> = {}): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/console/compatibility/langgraph/threads",
      payload,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async createCompatibilityRun(threadId: string, payload: Record<string, unknown>): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs`,
      payload,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async probeCompatibilityStream(threadId: string, payload: Record<string, unknown>): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs/stream-probe`,
      payload,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async joinCompatibilityRun(threadId: string, runId: ResourceId): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs/${runId}/join`,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async cancelCompatibilityRun(threadId: string, runId: ResourceId): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs/${runId}/cancel`,
    );
    return mapCompatibilityExplorerResult(response as Record<string, unknown>);
  },
  async createCompatibilityMigrationReport(payload: Record<string, unknown>): Promise<CompatibilityMigrationResponse> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/console/compatibility/migration-report",
      payload,
    );
    return mapCompatibilityMigrationResponse(response as Record<string, unknown>);
  },
  async getCompatibilityAssistant(assistantId: string): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient().listAdminCollection<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/assistants/${assistantId}`,
    ) as unknown as Record<string, unknown>;
    return mapCompatibilityExplorerResult(response);
  },
  async getCompatibilityThread(threadId: string): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient().listAdminCollection<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}`,
    ) as unknown as Record<string, unknown>;
    return mapCompatibilityExplorerResult(response);
  },
  async getCompatibilityRun(threadId: string, runId: ResourceId): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient().listAdminCollection<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs/${runId}`,
    ) as unknown as Record<string, unknown>;
    return mapCompatibilityExplorerResult(response);
  },
  async getCompatibilityStreamStatus(threadId: string, runId: ResourceId): Promise<CompatibilityExplorerResult> {
    const response = await nativeClient().listAdminCollection<Record<string, unknown>>(
      `/v1/console/compatibility/langgraph/threads/${threadId}/runs/${runId}/stream-status`,
    ) as unknown as Record<string, unknown>;
    return mapCompatibilityExplorerResult(response);
  },
  async replayCompatibilityEvents(
    threadId: string,
    runId: ResourceId,
    lastEventId: string,
  ): Promise<CompatibilityExplorerResult> {
    const baseUrl = apiBaseUrl();
    if (!baseUrl) {
      throw new Error("DimooRun API base URL is not configured.");
    }
    const response = await fetch(
      `${baseUrl}/v1/console/compatibility/langgraph/threads/${threadId}/runs/${runId}/events?last_event_id=${encodeURIComponent(lastEventId)}`,
      {
        method: "GET",
        headers: nativeHeaders(),
      },
    );
    if (!response.ok) {
      let detail: unknown = null;
      try {
        const body = await response.json() as { detail?: unknown };
        detail = body.detail ?? body;
      } catch {
        detail = { message: `HTTP ${response.status}` };
      }
      if (isRecord(detail)) {
        throw {
          errorCode: typeof detail.error_code === "string" ? detail.error_code : `http_${response.status}`,
          message: typeof detail.message === "string" ? detail.message : `HTTP ${response.status}`,
          requestId: typeof detail.request_id === "string" ? detail.request_id : null,
          details: isRecord(detail.details) ? detail.details : null,
        };
      }
      throw detail;
    }
    return mapCompatibilityExplorerResult(await response.json() as Record<string, unknown>);
  },
  async decideHumanTask(taskId: ResourceId, decision: "approve" | "reject", comment = ""): Promise<HumanTask> {
    const payload = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/human-tasks/${taskId}/${decision}`,
      { decision_payload: { source: "console", comment, decided_by: "console" } },
    );
    return mapAdminHumanTask(payload.item);
  },
  async simulatePolicy(draftPolicy: PolicyDraft, sample: Record<string, unknown>): Promise<PolicySimulation> {
    const payload = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/policies/simulate",
      { draft_policy: draftPolicy, sample },
    );
    return mapPolicySimulation(payload as Record<string, unknown>);
  },
  async activatePolicy(
    draftPolicy: PolicyDraft,
    auditReason: string,
    expectedVersion?: number | null,
  ): Promise<PolicyActivation> {
    const payload = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/policies/activate",
      { draft_policy: draftPolicy, audit_reason: auditReason, expected_version: expectedVersion ?? undefined },
    );
    return mapPolicyActivation(payload as Record<string, unknown>);
  },
  async rollbackPolicy(
    policyId: ResourceId,
    targetVersion: number,
    auditReason: string,
    expectedVersion?: number | null,
  ): Promise<PolicyActivation> {
    const payload = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      `/v1/policies/${policyId}/rollback`,
      { target_version: targetVersion, audit_reason: auditReason, expected_version: expectedVersion ?? undefined },
    );
    return mapPolicyActivation(payload as Record<string, unknown>);
  },
  async testModelGateway(payload: Record<string, unknown>): Promise<ModelGatewayTestResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/model-gateways/test",
      payload,
    );
    return mapModelGatewayTest(response as Record<string, unknown>);
  },
  async dryRunTool(payload: Record<string, unknown>): Promise<ToolDryRunResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/tools/dry-run",
      payload,
    );
    return mapToolDryRun(response as Record<string, unknown>);
  },
  async validateSecret(payload: Record<string, unknown>): Promise<SecretValidationResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/secrets/validate",
      payload,
    );
    return mapSecretValidation(response as Record<string, unknown>);
  },
  async rotateSecret(payload: Record<string, unknown>): Promise<SecretRotationResult> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<Record<string, unknown>>(
      "/v1/secrets/rotate",
      payload,
    );
    return mapSecretRotation(response as Record<string, unknown>);
  },
  async listAdminCollection(path: string, scopeOverride?: Partial<ConsoleScope>): Promise<CursorPage<AdminResource>> {
    const payload = await nativeClient(undefined, scopeOverride).listAdminCollection<AdminResource>(path);
    return page(payload.items);
  },
  async createAdminItem(path: string, payload: Record<string, unknown>): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).createAdminItem<AdminResource>(path, payload);
    return response.item;
  },
  async updateAdminItem(path: string, resourceId: ResourceId, payload: Record<string, unknown>): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).updateAdminItem<AdminResource>(path, resourceId, payload);
    return response.item;
  },
  async deleteAdminItem(path: string, resourceId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>(path, resourceId);
    return response.item;
  },
  async revokeOperatorSessions(operatorId: ResourceId): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/revoke-sessions`);
  },
  async listOperatorSessions(operatorId: ResourceId): Promise<CursorPage<ConsoleOperatorSession>> {
    const payload = await nativeClient().listAdminCollection<ConsoleOperatorSession>(`/v1/identity/operators/${operatorId}/sessions`);
    return page(payload.items);
  },
  async resetOperatorPassword(operatorId: ResourceId, newPassword: string): Promise<void> {
    await nativeClient(crypto.randomUUID()).postAdminAction(`/v1/identity/operators/${operatorId}/reset-password`, {
      new_password: newPassword,
    });
  },
  async deleteOperator(operatorId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>("/v1/identity/operators", operatorId);
    return response.item;
  },
  async listServiceAccounts(): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection("/v1/identity/service-accounts");
  },
  async createServiceAccount(payload: Record<string, unknown>): Promise<AdminResource> {
    return this.createAdminItem("/v1/identity/service-accounts", payload);
  },
  async updateServiceAccount(serviceAccountId: ResourceId, payload: Record<string, unknown>): Promise<AdminResource> {
    return this.updateAdminItem("/v1/identity/service-accounts", serviceAccountId, payload);
  },
  async deleteServiceAccount(serviceAccountId: ResourceId): Promise<AdminResource> {
    return this.deleteAdminItem("/v1/identity/service-accounts", serviceAccountId);
  },
  async listServiceAccountApiKeys(serviceAccountId: ResourceId): Promise<CursorPage<AdminResource>> {
    return this.listAdminCollection(`/v1/identity/service-accounts/${serviceAccountId}/api-keys`);
  },
  async getRolePermissionMatrix(): Promise<RolePermissionMatrix> {
    return requestConsolePath<RolePermissionMatrix>("/v1/console/identity/role-matrix");
  },
  async previewRoleMatrix(roleId: ResourceId, permissions: string[]): Promise<RolePermissionPreview> {
    const response = await requestConsolePath<{ item: RolePermissionPreview; request_id: string | null }>(
      `/v1/identity/workflows/roles/${roleId}/preview`,
      {
        method: "POST",
        body: JSON.stringify({ permissions }),
      },
    );
    return response.item;
  },
  async applyRoleMatrix(
    roleId: ResourceId,
    permissions: string[],
    auditReason: string,
  ): Promise<RolePermissionPreview> {
    const response = await requestConsolePath<{ item: RolePermissionPreview; request_id: string | null }>(
      `/v1/identity/workflows/roles/${roleId}/apply`,
      {
        method: "POST",
        body: JSON.stringify({ permissions }),
      },
      undefined,
      { auditReason },
    );
    return response.item;
  },
  async getOperatorAccessDetail(operatorId: ResourceId): Promise<OperatorAccessDetail> {
    return requestConsolePath<OperatorAccessDetail>(`/v1/console/identity/operators/${operatorId}`);
  },
  async revokeOwnConsoleSession(token: string): Promise<void> {
    await requestConsolePath<{ ok: boolean; request_id: string | null }>(
      "/v1/identity/workflows/sessions/revoke-self",
      {
        method: "POST",
        body: JSON.stringify({ token }),
      },
    );
  },
  async revokeOperatorSession(operatorId: ResourceId, sessionId: ResourceId): Promise<void> {
    await requestConsolePath<{ ok: boolean; request_id: string | null }>(
      `/v1/identity/workflows/operators/${operatorId}/sessions/${sessionId}/revoke`,
      {
        method: "POST",
      },
    );
  },
  async getServiceAccountDetail(serviceAccountId: ResourceId): Promise<ServiceAccountDetail> {
    return requestConsolePath<ServiceAccountDetail>(`/v1/console/identity/service-accounts/${serviceAccountId}`);
  },
  async createServiceAccountApiKey(serviceAccountId: ResourceId, payload: Record<string, unknown>): Promise<MachineApiKeyCreate> {
    return nativeClient(crypto.randomUUID()).createAdminItem<MachineApiKeyCreate["item"]>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys`,
      payload,
    ) as Promise<MachineApiKeyCreate>;
  },
  async disableServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys/${keyId}/disable`,
    );
    return response.item;
  },
  async enableServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).postAdminAction<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys/${keyId}/enable`,
    );
    return response.item;
  },
  async deleteServiceAccountApiKey(serviceAccountId: ResourceId, keyId: ResourceId): Promise<AdminResource> {
    const response = await nativeClient(crypto.randomUUID()).deleteAdminItem<AdminResource>(
      `/v1/identity/service-accounts/${serviceAccountId}/api-keys`,
      keyId,
    );
    return response.item;
  },
  async rotateServiceAccountApiKey(
    serviceAccountId: ResourceId,
    keyId: ResourceId,
    payload: Record<string, unknown>,
    auditReason: string,
  ): Promise<MachineApiKeyCreate & { rotated_from: AdminResource; scope_diff: Record<string, unknown> }> {
    return requestConsolePath<MachineApiKeyCreate & { rotated_from: AdminResource; scope_diff: Record<string, unknown> }>(
      `/v1/identity/workflows/service-accounts/${serviceAccountId}/api-keys/${keyId}/rotate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      undefined,
      { auditReason },
    );
  },
  async forceExpireServiceAccountApiKey(
    serviceAccountId: ResourceId,
    keyId: ResourceId,
    auditReason: string,
  ): Promise<AdminResource> {
    const response = await requestConsolePath<{ item: AdminResource; request_id: string | null }>(
      `/v1/identity/workflows/service-accounts/${serviceAccountId}/api-keys/${keyId}/force-expire`,
      {
        method: "POST",
      },
      undefined,
      { auditReason },
    );
    return response.item;
  },
  async getPlatformSettingsSnapshot(): Promise<PlatformSettingsSnapshot> {
    const response = await requestConsolePath<{ item: PlatformSettingsSnapshot; request_id: string | null }>(
      "/v1/console/settings/platform",
    );
    return response.item;
  },
  async listProviderStatuses(): Promise<ProviderStatus[]> {
    const response = await requestConsolePath<{ items: ProviderStatus[]; request_id: string | null }>(
      "/v1/console/settings/providers",
    );
    return response.items;
  },
  async listScopedPlatformSettings(): Promise<PlatformScopedSetting[]> {
    const response = await requestConsolePath<{ items: PlatformScopedSetting[]; request_id: string | null }>(
      "/v1/console/settings/scoped-defaults",
    );
    return response.items;
  },
  async updateScopedPlatformSettings(
    scopeKind: PlatformScopedSetting["scope_kind"],
    config: Record<string, unknown>,
    auditReason: string,
  ): Promise<PlatformScopedSetting> {
    const response = await requestConsolePath<{ item: PlatformScopedSetting; request_id: string | null }>(
      `/v1/console/settings/scoped-defaults/${scopeKind}`,
      {
        method: "POST",
        body: JSON.stringify({ config }),
      },
      undefined,
      { auditReason },
    );
    return response.item;
  },
  async preflightDangerousPlatformAction(action: string): Promise<DangerousActionPreview> {
    const response = await requestConsolePath<{ item: DangerousActionPreview; request_id: string | null }>(
      "/v1/console/settings/danger/preflight",
      {
        method: "POST",
        body: JSON.stringify({ action }),
      },
    );
    return response.item;
  },
  async runDangerousPlatformAction(
    action: string,
    payload: { confirmation: string; rollback_notes: string },
    auditReason: string,
  ): Promise<DangerousActionResult> {
    const response = await requestConsolePath<{ item: DangerousActionResult; request_id: string | null }>(
      `/v1/console/settings/danger/actions/${action}`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      undefined,
      { auditReason },
    );
    return response.item;
  },
};

export const consoleClient = liveConsoleClient;
