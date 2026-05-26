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
  thread_id: string | null;
};

export type NativeTaskCreateResponse = {
  run_id: string;
  task_id: string;
  status: string;
  replayed: boolean;
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
  ) {
    super(message);
    this.name = "DimooRunApiError";
  }
}

async function request<T>(options: ClientOptions, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${options.baseUrl.replace(/\/$/, "")}${path}`, {
    ...init,
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
    );
  }
  return payload as T;
}

export function createDimooRunClient(options: ClientOptions) {
  return {
    listAgents: () => request<NativeAgentRead[]>(options, "/v1/agents"),
    listDeployments: () => request<NativeDeploymentRead[]>(options, "/v1/deployments"),
    getRun: (runId: string) => request<NativeRunRead>(options, `/v1/runs/${runId}`),
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
