export type ResourceId = number;

export type NativeAgentRead = {
  id: ResourceId;
  name: string;
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
};

export type NativeTaskCreateResponse = {
  run_id: ResourceId;
  task_id: ResourceId;
  status: string;
  replayed: boolean;
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
    listDeployments: () => request<NativeDeploymentRead[]>(options, "/v1/deployments"),
    listRuns: () => request<NativeRunRead[]>(options, "/v1/runs"),
    getRun: (runId: ResourceId) => request<NativeRunRead>(options, `/v1/runs/${runId}`),
    listRunEvents: (runId: ResourceId) => request<NativeEventRead[]>(options, `/v1/runs/${runId}/events`),
    listRunAttempts: (runId: ResourceId) => request<Record<string, unknown>[]>(options, `/v1/runs/${runId}/attempts`),
    listTasks: () => request<NativeTaskRead[]>(options, "/v1/tasks"),
    controlDeployment: (deploymentId: ResourceId, operation: string) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}/${operation}`, {
        method: "POST",
      }),
    controlRun: (runId: ResourceId, operation: string) =>
      request<NativeRunRead>(options, `/v1/runs/${runId}/${operation}`, {
        method: "POST",
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
    createTask: (agentId: ResourceId, input: Record<string, unknown>, idempotencyKey: string) =>
      request<NativeTaskCreateResponse>(options, `/v1/agents/${agentId}/tasks`, {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ input }),
      }),
  };
}
