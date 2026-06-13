export type ResourceId = number;

export type NativeAgentRead = {
  id: ResourceId;
  name: string;
  description: string | null;
  status: string;
  created_at: string | null;
};

export type NativeAgentVersionRead = {
  id: ResourceId;
  agent_id: ResourceId;
  version: string;
  package_uri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  capabilities: Record<string, unknown>;
  manifest: Record<string, unknown>;
  status: string;
};

export type NativeDeploymentRead = {
  id: ResourceId;
  tenant_id: ResourceId;
  project_id: ResourceId;
  agent_id: ResourceId;
  agent_version_id: ResourceId;
  environment: string;
  desired_status: string;
  runtime_status: string;
  replicas: number;
  config: Record<string, unknown>;
  last_runtime_error: string | null;
};

export type NativeRunRead = {
  id: ResourceId;
  agent_id: ResourceId;
  agent_version_id: ResourceId;
  deployment_id: ResourceId | null;
  status: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  thread_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  latency_ms: number | null;
};

export type NativeTaskCreateResponse = {
  run_id: ResourceId;
  task_id: ResourceId;
  status: string;
  replayed: boolean;
};

export type NativeTaskCreatePayload = {
  input: Record<string, unknown>;
  version?: string | null;
  thread_id?: string | null;
};

export type NativeDeploymentCreatePayload = {
  agent_id: ResourceId;
  agent_version_id: ResourceId;
  environment: string;
  desired_status?: string;
  replicas?: number;
  config?: Record<string, unknown>;
};

export type NativeDeploymentUpdatePayload = {
  agent_version_id?: ResourceId | null;
  environment?: string | null;
  replicas?: number | null;
  config?: Record<string, unknown> | null;
};

export type NativeDeploymentTaskCreatePayload = {
  input: Record<string, unknown>;
  thread_id?: string | null;
};

export type DeploymentPromotionPreviewRead = {
  deployment_id: ResourceId;
  environment: string;
  desired_status: string;
  runtime_status: string;
  current_agent_version_id: ResourceId;
  candidate_agent_version_id: ResourceId;
  active_runs: number;
  queued_tasks: number;
  candidate_validation_status: string;
  rollback_agent_version_id: ResourceId | null;
  required_permissions: string[];
  audit_required: boolean;
  can_promote: boolean;
  blocked_reason: string | null;
  warnings: string[];
  quality_gate?: Record<string, unknown> | null;
};

export type DeploymentPromotePayload = {
  candidate_version_id: ResourceId;
  expected_current_version_id: ResourceId;
  experiment_run_id: ResourceId;
  rollout_reason: string;
};

export type DeploymentRollbackPayload = {
  expected_current_version_id: ResourceId;
  rollback_agent_version_id?: ResourceId | null;
  rollback_reason: string;
};

export type ReplayComparisonRequest = {
  source_run_id: ResourceId;
  candidate_agent_version_id?: ResourceId | null;
  replay_config?: Record<string, unknown>;
};

export type ReplayValueDiffRead = {
  changed: boolean;
  source: unknown;
  replay: unknown;
};

export type ReplayEventDiffRead = {
  changed: boolean;
  source_count: number;
  replay_count: number;
  added_types: string[];
  removed_types: string[];
};

export type ReplayComparisonRead = {
  comparison_id: string;
  source_run: NativeRunRead;
  replay_run: NativeRunRead;
  source_events: NativeEventRead[];
  replay_events: NativeEventRead[];
  input_diff: ReplayValueDiffRead;
  output_diff: ReplayValueDiffRead;
  error_diff: ReplayValueDiffRead;
  event_diff: ReplayEventDiffRead;
  latency_delta_ms: number | null;
  cost_delta_usd: number | null;
  regression_signal: string;
  provenance: Record<string, unknown>;
};

export type DatasetCapturePayload = {
  dataset_name: string;
  label?: string | null;
};

export type DatasetCaptureRead = {
  capture_id: string;
  comparison_id: string;
  dataset_name: string;
  label: string | null;
  source_run_id: ResourceId;
  replay_run_id: ResourceId;
  provenance: Record<string, unknown>;
};

export type PackageValidationPayload = {
  package_uri: string;
  framework: string;
  adapter: string;
  entrypoint: string;
  manifest: Record<string, unknown>;
  required_secret_refs?: string[];
};

export type PackageValidationRead = {
  status: string;
  ready: boolean;
  validation_token: string | null;
  errors: Array<{
    field: string;
    code: string;
    message: string;
  }>;
  warnings: string[];
  missing_secret_refs: string[];
  capabilities: Record<string, unknown>;
  next_action: string;
};

export type NativeTaskRead = {
  id: ResourceId;
  run_id: ResourceId;
  status: string;
  queue: string;
  priority: number;
  attempt: number;
  max_attempts: number;
  dead_letter_reason: string | null;
  partition_key: string | null;
  resource_class: string | null;
  quota_blocking_reason: Record<string, unknown> | null;
};

export type ConsoleDashboardSummaryRead = {
  run_count_today: number;
  success_rate: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  queue_backlog: number;
  worker_ready: number;
  worker_total: number;
  monthly_cost_usd: number;
  pending_approvals: number;
  running_runs: number;
  active_incidents: number;
};

export type ConsoleDeploymentHealthRead = {
  deployment_id: ResourceId;
  environment: string;
  desired_status: string;
  runtime_status: string;
  replicas: number;
  queue_backlog: number;
  running_runs: number;
  last_runtime_error: string | null;
};

export type ConsoleWorkerHealthRead = {
  worker_id: string;
  deployment_id: ResourceId;
  environment: string;
  status: string;
  queue_backlog: number;
  running_runs: number;
};

export type ConsoleRecentFailureRead = {
  run_id: ResourceId;
  deployment_id: ResourceId | null;
  agent_id: ResourceId;
  agent_version_id: ResourceId;
  status: string;
  error_summary: string;
  created_at: string;
};

export type ConsolePendingActionRead = {
  resource_type: string;
  resource_id: ResourceId;
  action: string;
  label: string;
  disabled_reason: string | null;
  required_permissions: string[];
  audit_required: boolean;
};

export type ConsoleActionAvailabilityRead = {
  resource_type: string;
  resource_id: ResourceId;
  action: string;
  available: boolean;
  disabled_reasons: string[];
  required_permissions: string[];
  policy_warnings: string[];
  audit_required: boolean;
};

export type ConsoleActionSummaryRead = {
  actions: ConsoleActionAvailabilityRead[];
};

export type ConsoleRuntimeOverviewRead = {
  summary: ConsoleDashboardSummaryRead;
  deployment_health: ConsoleDeploymentHealthRead[];
  worker_health: ConsoleWorkerHealthRead[];
  recent_failures: ConsoleRecentFailureRead[];
  pending_actions: ConsolePendingActionRead[];
};

export type AdminCollectionResponse<T = Record<string, unknown>> = {
  items: T[];
  count: number;
  request_id: string | null;
};

export type AdminItemResponse<T = Record<string, unknown>> = {
  item: T;
  request_id: string | null;
};

export type ConsoleOperatorRead = {
  id: ResourceId;
  email: string;
  name: string;
  roles: string[];
  permissions: string[];
  allowed_scopes: Array<{
    tenant_id: ResourceId;
    tenant_name?: string | null;
    project_id: ResourceId;
    project_name?: string | null;
    environment: string;
    environment_name?: string | null;
  }>;
  status: string;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  password_changed_at: string | null;
};

export type ConsoleLoginResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  operator: ConsoleOperatorRead;
  request_id: string | null;
};

export type NativeEventRead = {
  run_id: ResourceId;
  event_id: string;
  sequence: number;
  type: string;
  payload: Record<string, unknown>;
  visibility_level: string;
};

type ClientOptions = {
  baseUrl: string;
  headers: HeadersInit;
};

export class DimooRunApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly errorCode: string | null,
    readonly requestId: string | null,
    readonly details: Record<string, unknown> | null,
  ) {
    super(message);
    this.name = "DimooRunApiError";
  }
}

async function request<T>(options: ClientOptions, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${options.baseUrl.replace(/\/$/, "")}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...options.headers,
      ...init?.headers,
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const errorPayload = payload?.detail || payload;
    throw new DimooRunApiError(
      payload?.detail?.message || payload?.message || `DimooRun API request failed: ${response.status}`,
      response.status,
      payload?.detail?.error_code || errorPayload?.error_code || null,
      payload?.detail?.request_id || errorPayload?.request_id || null,
      payload?.detail?.details || errorPayload?.details || null,
    );
  }
  return payload as T;
}

export function createDimooRunClient(options: ClientOptions) {
  return {
    listAgents: () => request<NativeAgentRead[]>(options, "/v1/agents"),
    validatePackage: (payload: PackageValidationPayload) =>
      request<PackageValidationRead>(options, "/v1/packages/validate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getConsoleDashboardSummary: () =>
      request<ConsoleDashboardSummaryRead>(options, "/v1/console/dashboard-summary"),
    getConsoleRuntimeOverview: () =>
      request<ConsoleRuntimeOverviewRead>(options, "/v1/console/runtime-overview"),
    listConsoleDeploymentHealth: () =>
      request<ConsoleDeploymentHealthRead[]>(options, "/v1/console/deployment-health"),
    listConsoleWorkerHealth: () =>
      request<ConsoleWorkerHealthRead[]>(options, "/v1/console/worker-health"),
    listConsoleRecentFailures: () =>
      request<ConsoleRecentFailureRead[]>(options, "/v1/console/recent-failures"),
    listConsolePendingActions: () =>
      request<ConsolePendingActionRead[]>(options, "/v1/console/pending-actions"),
    getConsoleActionSummary: (resourceType?: string, resourceId?: ResourceId) => {
      const params = new URLSearchParams();
      if (resourceType) params.set("resource_type", resourceType);
      if (resourceId !== undefined) params.set("resource_id", String(resourceId));
      const query = params.toString();
      return request<ConsoleActionSummaryRead>(
        options,
        `/v1/console/action-summary${query ? `?${query}` : ""}`,
      );
    },
    login: (email: string, password: string) =>
      request<ConsoleLoginResponse>(options, "/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    me: () => request<{ operator: ConsoleOperatorRead; request_id: string | null }>(options, "/v1/auth/me"),
    logout: () =>
      request<{ ok: boolean }>(options, "/v1/auth/logout", {
        method: "POST",
      }),
    changePassword: (currentPassword: string, newPassword: string) =>
      request<{ ok: boolean; request_id: string | null }>(options, "/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
    createAgent: (payload: Record<string, unknown>) =>
      request<NativeAgentRead>(options, "/v1/agents", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateAgent: (agentId: ResourceId, payload: Record<string, unknown>) =>
      request<NativeAgentRead>(options, `/v1/agents/${agentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    archiveAgent: (agentId: ResourceId) =>
      request<NativeAgentRead>(options, `/v1/agents/${agentId}`, {
        method: "DELETE",
      }),
    createAgentVersion: (agentId: ResourceId, payload: Record<string, unknown>) =>
      request<NativeAgentVersionRead>(options, `/v1/agents/${agentId}/versions`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    listAgentVersions: (agentId: ResourceId) =>
      request<NativeAgentVersionRead[]>(options, `/v1/agents/${agentId}/versions`),
    updateAgentVersion: (agentId: ResourceId, version: string, payload: Record<string, unknown>) =>
      request<NativeAgentVersionRead>(options, `/v1/agents/${agentId}/versions/${encodeURIComponent(version)}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    archiveAgentVersion: (agentId: ResourceId, version: string) =>
      request<NativeAgentVersionRead>(options, `/v1/agents/${agentId}/versions/${encodeURIComponent(version)}`, {
        method: "DELETE",
      }),
    listDeployments: () => request<NativeDeploymentRead[]>(options, "/v1/deployments"),
    createDeployment: (payload: NativeDeploymentCreatePayload) =>
      request<NativeDeploymentRead>(options, "/v1/deployments", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateDeployment: (deploymentId: ResourceId, payload: NativeDeploymentUpdatePayload) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    archiveDeployment: (deploymentId: ResourceId) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}`, {
        method: "DELETE",
      }),
    listRuns: () => request<NativeRunRead[]>(options, "/v1/runs"),
    getRun: (runId: ResourceId) => request<NativeRunRead>(options, `/v1/runs/${runId}`),
    listRunEvents: (runId: ResourceId) => request<NativeEventRead[]>(options, `/v1/runs/${runId}/events`),
    listEvents: () => request<NativeEventRead[]>(options, "/v1/events"),
    listRunAttempts: (runId: ResourceId) => request<Record<string, unknown>[]>(options, `/v1/runs/${runId}/attempts`),
    listTasks: () => request<NativeTaskRead[]>(options, "/v1/tasks"),
    controlDeployment: (deploymentId: ResourceId, operation: string) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}/${operation}`, {
        method: "POST",
      }),
    getDeploymentPromotionPreview: (
      deploymentId: ResourceId,
      candidateVersionId: ResourceId,
      experimentRunId?: ResourceId | null,
    ) =>
      request<DeploymentPromotionPreviewRead>(
        options,
        `/v1/deployments/${deploymentId}/promotion-preview?candidate_version_id=${candidateVersionId}${experimentRunId ? `&experiment_run_id=${experimentRunId}` : ""}`,
      ),
    promoteDeployment: (deploymentId: ResourceId, payload: DeploymentPromotePayload) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}/promote`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    rollbackDeployment: (deploymentId: ResourceId, payload: DeploymentRollbackPayload) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}/rollback`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    controlRun: (runId: ResourceId, operation: string) =>
      request<NativeRunRead>(options, `/v1/runs/${runId}/${operation}`, {
        method: "POST",
      }),
    replayRun: (runId: ResourceId, payload: { agent_version_id?: ResourceId | null } = {}) =>
      request<NativeRunRead>(options, `/v1/runs/${runId}/replay`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createReplayComparison: (payload: ReplayComparisonRequest) =>
      request<ReplayComparisonRead>(options, "/v1/replay-jobs/compare", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    captureReplayDataset: (comparisonId: string, payload: DatasetCapturePayload) =>
      request<DatasetCaptureRead>(options, `/v1/replay-jobs/${comparisonId}/dataset-captures`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    cancelTask: (taskId: ResourceId) =>
      request<Record<string, unknown>>(options, `/v1/tasks/${taskId}/cancel`, {
        method: "POST",
      }),
    listAdminCollection: <T = Record<string, unknown>>(path: string) =>
      request<AdminCollectionResponse<T>>(options, path),
    createAdminItem: <T = Record<string, unknown>>(path: string, payload: Record<string, unknown>) =>
      request<AdminItemResponse<T>>(options, path, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    updateAdminItem: <T = Record<string, unknown>>(path: string, resourceId: ResourceId, payload: Record<string, unknown>) =>
      request<AdminItemResponse<T>>(options, `${path}/${resourceId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deleteAdminItem: <T = Record<string, unknown>>(path: string, resourceId: ResourceId) =>
      request<AdminItemResponse<T>>(options, `${path}/${resourceId}`, {
        method: "DELETE",
      }),
    postAdminAction: <T = Record<string, unknown>>(path: string, payload: Record<string, unknown> = {}) =>
      request<AdminItemResponse<T>>(options, path, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createTask: (agentId: ResourceId, payload: NativeTaskCreatePayload, idempotencyKey: string) =>
      request<NativeTaskCreateResponse>(options, `/v1/agents/${agentId}/tasks`, {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      }),
    createDeploymentTask: (deploymentId: ResourceId, payload: NativeDeploymentTaskCreatePayload, idempotencyKey: string) =>
      request<NativeTaskCreateResponse>(options, `/v1/deployments/${deploymentId}/tasks`, {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(payload),
      }),
  };
}
