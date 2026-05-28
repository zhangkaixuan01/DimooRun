export type NativeAgentRead = {
  id: string;
  name: string;
  status: string;
};

export type NativeDeploymentRead = {
  id: string;
  tenant_id: string;
  project_id: string;
  agent_id: string;
  agent_version_id: string;
  environment: string;
  desired_status: string;
  runtime_status: string;
  replicas: number;
  last_runtime_error: string | null;
};

export type NativeRunRead = {
  id: string;
  agent_id: string;
  agent_version_id: string;
  deployment_id: string | null;
  status: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  error?: Record<string, unknown> | null;
  thread_id: string | null;
};

export type NativeTaskCreateResponse = {
  run_id: string;
  task_id: string;
  status: string;
  replayed: boolean;
};

export type NativeTaskRead = {
  id: string;
  run_id: string;
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
  id: string;
  email: string;
  name: string;
  roles: string[];
  permissions: string[];
  allowed_scopes: Array<{
    tenant_id: string;
    project_id: string;
    environment: string;
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
    throw new DimooRunApiError(
      payload?.message || `DimooRun API request failed: ${response.status}`,
      response.status,
      payload?.error_code || null,
      payload?.request_id || null,
      payload?.details || null,
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
    updateAgent: (agentId: string, payload: Record<string, unknown>) =>
      request<NativeAgentRead>(options, `/v1/agents/${agentId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    archiveAgent: (agentId: string) =>
      request<NativeAgentRead>(options, `/v1/agents/${agentId}`, {
        method: "DELETE",
      }),
    listDeployments: () => request<NativeDeploymentRead[]>(options, "/v1/deployments"),
    listRuns: () => request<NativeRunRead[]>(options, "/v1/runs"),
    getRun: (runId: string) => request<NativeRunRead>(options, `/v1/runs/${runId}`),
    listRunEvents: (runId: string) => request<NativeEventRead[]>(options, `/v1/runs/${runId}/events`),
    listRunAttempts: (runId: string) => request<Record<string, unknown>[]>(options, `/v1/runs/${runId}/attempts`),
    listTasks: () => request<NativeTaskRead[]>(options, "/v1/tasks"),
    controlDeployment: (deploymentId: string, operation: string) =>
      request<NativeDeploymentRead>(options, `/v1/deployments/${deploymentId}/${operation}`, {
        method: "POST",
      }),
    controlRun: (runId: string, operation: string) =>
      request<NativeRunRead>(options, `/v1/runs/${runId}/${operation}`, {
        method: "POST",
      }),
    cancelTask: (taskId: string) =>
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
    updateAdminItem: <T = Record<string, unknown>>(path: string, resourceId: string, payload: Record<string, unknown>) =>
      request<AdminItemResponse<T>>(options, `${path}/${resourceId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    deleteAdminItem: <T = Record<string, unknown>>(path: string, resourceId: string) =>
      request<AdminItemResponse<T>>(options, `${path}/${resourceId}`, {
        method: "DELETE",
      }),
    postAdminAction: <T = Record<string, unknown>>(path: string, payload: Record<string, unknown> = {}) =>
      request<AdminItemResponse<T>>(options, path, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    createTask: (agentId: string, input: Record<string, unknown>, idempotencyKey: string) =>
      request<NativeTaskCreateResponse>(options, `/v1/agents/${agentId}/tasks`, {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ input }),
      }),
  };
}
