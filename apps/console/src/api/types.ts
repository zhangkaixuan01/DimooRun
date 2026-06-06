export type StatusTone = "success" | "warning" | "danger" | "neutral" | "running" | "disabled";
export type ResourceId = number;

export type ConsoleWriteOptions = {
  auditReason?: string;
};

export type Agent = {
  id: ResourceId;
  name: string;
  description: string | null;
  status: string;
  createdAt: string | null;
  versionCount: number;
  deploymentCount: number;
};

export type AgentVersion = {
  id: ResourceId;
  agentId: ResourceId;
  version: string;
  packageUri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  capabilities: Record<string, unknown>;
  manifest: Record<string, unknown>;
  status: string;
};

export type Deployment = {
  id: ResourceId;
  agent: string;
  version: string;
  environment: string;
  desiredStatus: "active" | "paused" | "draining" | "stopped";
  runtimeStatus: "ready" | "degraded" | "warming_up";
  instances: number;
  config: Record<string, unknown>;
  runningRuns: number;
  queueBacklog: number;
  worker: string;
  heartbeatAt: string;
  executionProfile: string;
  modelGateway: string;
};

export type Run = {
  id: ResourceId;
  agent: string;
  framework: string;
  adapter: string;
  version: string;
  actor: string;
  status: "succeeded" | "failed" | "running" | "timeout" | "cancelled";
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  latencyMs: number | null;
  costUsd?: number;
  trigger: "api" | "schedule" | "replay" | "batch" | "compatibility";
  deployment: string;
  traceId: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
};

export type RuntimeEvent = {
  runId: ResourceId;
  sequence: number;
  eventId: string;
  type: string;
  status: string;
  timestamp?: string;
  summary: string;
  payload?: Record<string, unknown>;
};

export type RunAttempt = {
  id: ResourceId;
  runId: ResourceId;
  taskId: ResourceId | null;
  attemptNo: number;
  workerId: string | null;
  status: string;
  error: string | null;
};

export type Task = {
  id: ResourceId;
  runId: ResourceId;
  status: "queued" | "leased" | "running" | "retrying" | "dead_letter" | "succeeded" | "cancelled";
  attempt: number;
  queue: string;
  workerId: string;
  heartbeatAt: string;
  leaseUntil: string;
  fencingToken: number;
  retryCount: number;
  deadLetterReason?: string;
  partitionKey?: string;
  resourceClass?: string;
  quotaBlockingReason?: {
    errorCode: string;
    scope: string;
    limit: number;
    current: number;
  };
};

export type TaskCreateResult = {
  runId: ResourceId;
  taskId: ResourceId;
  status: string;
  replayed: boolean;
};

export type DeploymentPromotionPreview = {
  deploymentId: ResourceId;
  environment: string;
  desiredStatus: string;
  runtimeStatus: string;
  currentAgentVersionId: ResourceId;
  candidateAgentVersionId: ResourceId;
  activeRuns: number;
  queuedTasks: number;
  candidateValidationStatus: string;
  rollbackAgentVersionId: ResourceId | null;
  requiredPermissions: string[];
  auditRequired: boolean;
  canPromote: boolean;
  blockedReason: string | null;
  warnings: string[];
};

export type ReplayValueDiff = {
  changed: boolean;
  source: unknown;
  replay: unknown;
};

export type ReplayEventDiff = {
  changed: boolean;
  sourceCount: number;
  replayCount: number;
  addedTypes: string[];
  removedTypes: string[];
};

export type ReplayComparison = {
  comparisonId: string;
  sourceRun: Run;
  replayRun: Run;
  sourceEvents: RuntimeEvent[];
  replayEvents: RuntimeEvent[];
  inputDiff: ReplayValueDiff;
  outputDiff: ReplayValueDiff;
  errorDiff: ReplayValueDiff;
  eventDiff: ReplayEventDiff;
  latencyDeltaMs: number | null;
  costDeltaUsd: number | null;
  regressionSignal: string;
  provenance: Record<string, unknown>;
};

export type DatasetCapture = {
  captureId: string;
  comparisonId: string;
  datasetName: string;
  label: string | null;
  sourceRunId: ResourceId;
  replayRunId: ResourceId;
  provenance: Record<string, unknown>;
};

export type RunDatasetCapture = {
  datasetId: ResourceId;
  datasetName: string;
  datasetItemId: ResourceId;
  sourceRunId: ResourceId;
  label: string | null;
  payloadPreview: Record<string, unknown>;
  redaction: Record<string, unknown>;
  provenance: Record<string, unknown>;
  audit: Record<string, unknown>;
  duplicate: boolean;
};

export type ExperimentRunResult = {
  experiment: Record<string, unknown>;
  run: Record<string, unknown>;
  results: Array<Record<string, unknown>>;
  scoreDistribution: Record<string, unknown>;
  qualityGate: Record<string, unknown>;
  audit: Record<string, unknown>;
};

export type QualityGatePreview = {
  status: string;
  promotionAllowed: boolean;
  blockedReason: string | null;
  requiredEvidence: string[];
  evidence: Record<string, unknown>;
  audit: Record<string, unknown>;
};

export type IncidentWorkflowResult = {
  incident: Record<string, unknown>;
  timeline: Array<Record<string, unknown>>;
  linkedEvidence: Record<string, unknown>;
  deliveryAttempts: Array<Record<string, unknown>>;
  resolution: Record<string, unknown> | null;
  audit: Record<string, unknown>;
};

export type NotificationTestResult = {
  status: string;
  deliveryAttempt: Record<string, unknown>;
  audit: Record<string, unknown>;
};

export type BackupDryRunResult = {
  status: string;
  scopeProof: Record<string, unknown>;
  validation: Record<string, unknown>;
  audit: Record<string, unknown>;
};

export type RestoreDryRunResult = BackupDryRunResult & {
  backupRef: string | null;
};

export type PublishValidationResult = {
  status: string;
  canPublish: boolean;
  checks: Record<string, Record<string, unknown>>;
  blockedReasons: string[];
  audit: Record<string, unknown>;
};

export type PublishedSurfacePublishResult = PublishValidationResult & {
  surface: Record<string, unknown>;
  rollout: Record<string, unknown>;
};

export type IngressRouteTestResult = {
  status: string;
  matchedDeployment: Record<string, unknown>;
  authDecision: Record<string, unknown>;
  policyDecision: Record<string, unknown>;
  expectedRuntimeTask: Record<string, unknown>;
  blockedReasons: string[];
  requestLog: Record<string, unknown>;
  audit: Record<string, unknown>;
};

export type PublishedSurfaceDetail = {
  surface: Record<string, unknown>;
  deploymentBindingHealth: Record<string, unknown>;
  requestLogs: Array<Record<string, unknown>>;
  rolloutHistory: Array<Record<string, unknown>>;
  actions: Record<string, unknown>;
};

export type PublishedSurfaceRolloutResult = {
  surface: Record<string, unknown>;
  rollout: Record<string, unknown>;
  rolloutHistory: Array<Record<string, unknown>>;
  audit: Record<string, unknown>;
};

export type ConsolePendingAction = {
  resourceType: string;
  resourceId: ResourceId;
  action: string;
  label: string;
  disabledReason: string | null;
  requiredPermissions: string[];
  auditRequired: boolean;
};

export type ConsoleRecentFailure = {
  runId: ResourceId;
  deploymentId: ResourceId | null;
  agentId: ResourceId;
  agentVersionId: ResourceId;
  status: string;
  errorSummary: string;
  createdAt: string;
};

export type ConsoleRuntimeOverview = {
  summary: {
    runCountToday: number;
    successRate: number;
    p95LatencyMs: number;
    p99LatencyMs: number;
    queueBacklog: number;
    workerReady: number;
    workerTotal: number;
    monthlyCostUsd: number;
    pendingApprovals: number;
    runningRuns: number;
    activeIncidents: number;
  };
  recentFailures: ConsoleRecentFailure[];
  pendingActions: ConsolePendingAction[];
  trendPoints: Array<{
    label: string;
    runs: number;
    successRate: number;
  }>;
};

export type PackageValidationResult = {
  status: string;
  ready: boolean;
  validationToken: string | null;
  errors: Array<{
    field: string;
    code: string;
    message: string;
  }>;
  warnings: string[];
  missingSecretRefs: string[];
  capabilities: Record<string, unknown>;
  nextAction: string;
};

export type HumanTask = {
  id: ResourceId;
  source: string;
  risk: "medium" | "high" | "critical";
  status: "pending" | "approved" | "rejected";
  assignee: string;
  requester: string;
  riskReason: string;
  decisionContext: Record<string, unknown>;
  diff: Record<string, unknown>;
  decision: {
    comment: string | null;
    decidedBy: string | null;
  };
  resumeOutcome: {
    status: string;
    taskId: ResourceId;
    decision?: string;
  };
  expiresAt: string;
};

export type PolicyDraft = {
  name: string;
  type: string;
  resource_type: string;
  action: string;
  decision: string;
  priority: number;
  risk_level: string;
  condition: Record<string, unknown>;
  reason: string;
};

export type PolicySimulation = {
  decision: {
    result: string;
    policyId: ResourceId | null;
    policyName: string | null;
    reason: string | null;
  };
  matchedResources: Array<{
    resourceType: string;
    resourceId: ResourceId | null;
    action: string;
    environment: string | null;
  }>;
  auditPreview: Record<string, unknown>;
  conflictWarnings: Array<Record<string, unknown>>;
};

export type PolicyActivation = {
  item: Record<string, unknown>;
  version: number;
  audit: Record<string, unknown>;
  rollbackTarget: {
    policyId: ResourceId;
    version: number;
  };
  conflictWarnings: Array<Record<string, unknown>>;
};

export type ModelGatewayTestResult = {
  credentialValidation: Record<string, unknown>;
  safeHealthProbe: Record<string, unknown>;
  budgetPreview: Record<string, unknown>;
  fallbackPreview: Record<string, unknown>;
  providerErrorNormalization: Record<string, unknown>;
  auditPreview: Record<string, unknown>;
};

export type ToolDryRunResult = {
  schemaValidation: Record<string, unknown>;
  riskClassification: Record<string, unknown>;
  policyPreview: Record<string, unknown>;
  approvalRequirement: Record<string, unknown>;
  usageHistoryLink: string;
  auditPreview: Record<string, unknown>;
};

export type SecretValidationResult = {
  validation: Record<string, unknown>;
  secretValue: null;
  lastUsed: Record<string, unknown>;
  accessAudit: Record<string, unknown>;
};

export type SecretRotationResult = {
  rotation: Record<string, unknown>;
  lastUsed: Record<string, unknown>;
  accessAudit: Record<string, unknown>;
};
